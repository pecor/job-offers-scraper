import re
import logging
from urllib.parse import urlparse, urlunparse
from datetime import date

logger = logging.getLogger(__name__)


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing query parameters and fragments.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    try:
        parsed = urlparse(url)
        # Remove query and fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            '',  # Remove query
            ''   # Remove fragment
        ))
        return normalized
    except Exception as e:
        logger.error(f"Error normalizing URL {url}: {e}")
        return url


def extract_salary(text: str) -> dict[str, float]:
    """
    Extract salary information from text.

    Args:
        text: Text containing salary information

    Returns:
        Dictionary with salary_min, salary_max, and salary_period
    """
    result = {
        'salary_min': None,
        'salary_max': None,
        'salary_period': None
    }

    if not text:
        return result

    # Patterns for salary extraction
    # Examples: "10 000 - 15 000 PLN/mies.", "5000-8000 PLN", "15k-20k PLN"
    patterns = [
        # Range with spaces: "10 000 - 15 000 PLN/mies."
        r'(\d+(?:\s?\d{3})*)\s*-\s*(\d+(?:\s?\d{3})*)\s*(?:PLN|zł)(?:/mies\.?|/miesiąc)?',
        # Range without spaces: "5000-8000 PLN"
        r'(\d+)\s*-\s*(\d+)\s*(?:PLN|zł)(?:/mies\.?|/miesiąc)?',
        # K notation: "15k-20k PLN"
        r'(\d+)k\s*-\s*(\d+)k\s*(?:PLN|zł)',
        # Single value: "10 000 PLN/mies."
        r'(\d+(?:\s?\d{3})*)\s*(?:PLN|zł)(?:/mies\.?|/miesiąc)?',
    ]

    _ = text.upper()
    text_lower = text.lower()
    
    is_hourly = False
    if any(indicator in text_lower for indicator in ['/h', '/godz', 'godzin', 'na godzinę', 'za godzinę', 'stawka godzinowa']):
        is_hourly = True
        result['salary_period'] = 'hour'
    elif any(indicator in text_lower for indicator in ['/mies', 'miesiąc', 'miesięcznie', 'na miesiąc']):
        result['salary_period'] = 'month'
    else:
        # Default = month
        result['salary_period'] = 'month'

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                # Range
                min_val = _parse_number(groups[0])
                max_val = _parse_number(groups[1])
                result['salary_min'] = min_val
                result['salary_max'] = max_val
            elif len(groups) == 1:
                # Single value
                val = _parse_number(groups[0])
                result['salary_min'] = val
                result['salary_max'] = val
            
            if is_hourly:
                result['salary_period'] = 'hour'
            break

    return result


def _parse_number(text: str) -> float:
    text = text.replace(' ', '')
    if text.lower().endswith('k'):
        return float(text[:-1]) * 1000
    
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_valid_until_date(date_text: str) -> str:
    """
    Parse date from text like "to 21 Feb" or "do 19 lut" into ISO format date string.
    If the date is in the past relative to current month, assumes next year.
    
    Args:
        date_text: Text containing date like "to 21 Feb" or "do 19 lut"
    
    Returns:
        ISO format date string (YYYY-MM-DD) or None if parsing failed
    """
    if not date_text:
        return None
    
    polish_months = {
        'sty': 1, 'stycznia': 1, 'styczeń': 1,
        'lut': 2, 'lutego': 2, 'luty': 2,
        'mar': 3, 'marca': 3, 'marzec': 3,
        'kwi': 4, 'kwietnia': 4, 'kwiecień': 4,
        'maj': 5, 'maja': 5,
        'cze': 6, 'czerwca': 6, 'czerwiec': 6,
        'lip': 7, 'lipca': 7, 'lipiec': 7,
        'sie': 8, 'sierpnia': 8, 'sierpień': 8,
        'wrz': 9, 'września': 9, 'wrzesień': 9,
        'paź': 10, 'października': 10, 'październik': 10,
        'lis': 11, 'listopada': 11, 'listopad': 11,
        'gru': 12, 'grudnia': 12, 'grudzień': 12,
    }
    
    english_months = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }
    
    pattern = r'(?:to|do)\s+(\d+)\s+([a-ząćęłńóśźż]+)'
    match = re.search(pattern, date_text.lower())
    
    if not match:
        return None
    
    try:
        day = int(match.group(1))
        month_name = match.group(2).lower().strip()
        
        month = polish_months.get(month_name)
        if month is None:
            month = english_months.get(month_name)
        
        if month is None:
            return None
        
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        # If the month is before current month, assume next year
        # If it's the same month but day is in the past, also assume next year
        if month < current_month or (month == current_month and day < today.day):
            year = current_year + 1
        else:
            year = current_year
        
        result_date = date(year, month, day)
        return result_date.isoformat()
        
    except (ValueError, KeyError) as e:
        logger.debug(f"Error parsing date '{date_text}': {e}")
        return None