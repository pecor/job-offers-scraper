import logging
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Any
from urllib.parse import urljoin, quote

from scrapers.base_scraper import BaseScraper
from utils.helpers import clean_text, extract_salary, normalize_url, parse_valid_until_date
from utils.utils import get_random_user_agent
from .config import (
    SELECTORS, CONTRACT_TYPE_KEYWORDS, DESCRIPTION_REMOVE_PATTERNS, DESCRIPTION_REMOVE_REGEX
)

logger = logging.getLogger(__name__)


class PracujPlScraper(BaseScraper):
    """pracuj.pl job portal scraper"""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize pracuj.pl scraper.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': get_random_user_agent()})
        self.delay = config.get('delay', 0.5) if config else 0.5
        
        domain = config.get('pracuj_pl_domain', 'it') if config else 'it'
        if domain == 'www':
            self.base_url = "https://www.pracuj.pl"
            self.search_url_template = "https://www.pracuj.pl/praca/{keyword};kw"
        else:
            self.base_url = "https://it.pracuj.pl"
            self.search_url_template = "https://it.pracuj.pl/praca/{keyword};kw"

    def _get_page(self, url: str) -> BeautifulSoup | None:
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'lxml')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def search_offers(self, keyword: str, max_pages: int) -> list[str]:
        urls = []
        page = 1

        while page <= max_pages:
            # sc=0 means sort by newest, pn is page number
            encoded_keyword = quote(keyword, safe='')
            search_url = f"{self.search_url_template.format(keyword=encoded_keyword)}?sc=0&pn={page}"
            logger.info(f"Scraping page {page}: {search_url}")

            soup = self._get_page(search_url)
            if not soup:
                break

            offer_links = soup.find_all('a', SELECTORS['offer_link'])
            
            if not offer_links:
                logger.info(f"No offers found on page {page}, stopping")
                break

            for link in offer_links:
                href = link.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    normalized = normalize_url(full_url)
                    if normalized not in urls:
                        urls.append(normalized)

            page += 1

        return urls

    def scrape_page_by_page(self, keyword: str, max_pages: int, db_manager=None, excluded_keywords: list[str] | None = None) -> int:
        """
        Scrape offers page by page, parsing and saving each offer immediately.

        Args:
            keyword: Search keyword
            max_pages: Maximum number of pages to scrape
            db_manager: Database manager instance for saving offers
            excluded_keywords: List of keywords to exclude

        Returns:
            Number of saved offers
        """
        excluded_keywords = excluded_keywords or []
        saved_count = 0
        page = 1

        while page <= max_pages:
            encoded_keyword = quote(keyword, safe='')
            search_url = f"{self.search_url_template.format(keyword=encoded_keyword)}?sc=0&pn={page}"
            logger.info(f"Scraping page {page}: {search_url}")

            soup = self._get_page(search_url)
            if not soup:
                break

            offer_links = soup.find_all('a', SELECTORS['offer_link'])
            
            if not offer_links:
                logger.info(f"No offers found on page {page}, stopping")
                break

            logger.info(f"Found {len(offer_links)} offers on page {page}")

            # Parse each offer on this page
            for link in offer_links:
                href = link.get('href')
                if not href:
                    continue

                full_url = urljoin(self.base_url, href)
                normalized_url = normalize_url(full_url)

                # Parse offer
                try:
                    offer = self.parse_offer(normalized_url)
                    if not offer:
                        continue

                    offer['source'] = self.source_name

                    # Filter excluded keywords
                    title_lower = offer.get('title', '').lower()
                    desc_lower = offer.get('description', '').lower()

                    should_exclude = False
                    for excluded in excluded_keywords:
                        if excluded.lower() in title_lower or excluded.lower() in desc_lower:
                            should_exclude = True
                            logger.debug(f"Excluding offer: {offer.get('title')} (matched: {excluded})")
                            break

                    if should_exclude:
                        continue

                    # Save to database
                    if db_manager and db_manager.insert_offer(offer):
                        saved_count += 1
                        logger.info(f"Saved: {offer.get('title', 'Unknown')}")

                except Exception as e:
                    logger.error(f"Error processing offer {normalized_url}: {e}")

            page += 1

        return saved_count

    def _remove_unwanted_text(self, text: str) -> str:
        """Remove unwanted patterns from text."""
        for pattern in DESCRIPTION_REMOVE_PATTERNS:
            text = text.replace(pattern, '')
        
        for pattern in DESCRIPTION_REMOVE_REGEX:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_company(self, soup: BeautifulSoup) -> str:
        """Extract company name from offer page using data-test attribute."""
        company_elem = soup.find('h2', {'data-test': 'text-employerName'})
        if company_elem:
            company_clone = BeautifulSoup(str(company_elem), 'lxml')
            for a_tag in company_clone.find_all('a'):
                a_tag.decompose()
            company = clean_text(company_clone.get_text())
            if company:
                return company
        
        return ""

    def _extract_location(self, soup: BeautifulSoup) -> str:
        """Extract location from offer page."""
        workplaces_elem = soup.find('li', {'data-test': 'sections-benefit-workplaces'})
        if workplaces_elem:
            badge_title = workplaces_elem.find('div', {'data-test': 'offer-badge-title'})
            if badge_title:
                location = clean_text(badge_title.get_text())
                location = re.sub(r'\s*\([^)]+\)\s*$', '', location).strip()
                if location:
                    if ',' in location:
                        parts = [p.strip() for p in location.split(',')]
                        city = parts[-1]
                        return city
                    else:
                        return location
        
        workplaces_wp_elem = soup.find('li', {'data-test': 'sections-benefit-workplaces-wp'})
        if workplaces_wp_elem:
            badge_title = workplaces_wp_elem.find('div', {'data-test': 'offer-badge-title'})
            if badge_title:
                location = clean_text(badge_title.get_text())
                location = re.sub(r'\s*\([^)]+\)\s*$', '', location).strip()
                # Extract only city name (last part after comma, or whole if no comma)
                if location:
                    if ',' in location:
                        parts = [p.strip() for p in location.split(',')]
                        city = parts[-1]
                        return city
                    else:
                        return location
        
        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract clean description from offer page"""
        description_parts = []
        
        section_data_tests = [
            'section-about-project',  # O projekcie / About the project
            'text-about-project',     # Alternative format
            'section-responsibilities',  # Twój zakres obowiązków / Your responsibilities
            'section-requirements',   # Nasze wymagania / Requirements
            'section-offer',          # Oferujemy / What we offer
        ]
        
        for section_test in section_data_tests:
            sections = soup.find_all(['section', 'div', 'ul'], {'data-test': section_test})
            
            for section in sections:
                bullet_lists = section.find_all('ul', {'data-test': lambda x: x and ('bullet' in str(x).lower() or 'aggregate' in str(x).lower())})
                
                if bullet_lists:
                    for ul in bullet_lists:
                        list_items = ul.find_all('li')
                        for item in list_items:
                            for svg in item.find_all('svg'):
                                svg.decompose()
                            for span in item.find_all('span', class_=lambda x: x and 'icon' in str(x).lower()):
                                span.decompose()
                            
                            text = item.get_text(separator=' ', strip=True)
                            text = clean_text(text)
                            
                            if (text and len(text) > 15 and 
                                not text.endswith(':') and
                                not any(word in text.lower()[:30] for word in [
                                    'przejdź', 'zobacz', 'zapisz', 'aplikuj', 'oferty pracy',
                                    'valid for', 'ważna jeszcze', 'company location', 'check how',
                                    'location:', 'working hours:', 'type of project:', 'type of employment'
                                ]) and
                                not re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+ \d+', text)):  # Not an address
                                description_parts.append(text)
                
                if not bullet_lists:
                    for header in section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        header.decompose()
                    
                    list_items = section.find_all('li')
                    
                    for item in list_items:
                        for svg in item.find_all('svg'):
                            svg.decompose()
                        for span in item.find_all('span', class_=lambda x: x and 'icon' in str(x).lower()):
                            span.decompose()
                        
                        text = item.get_text(separator=' ', strip=True)
                        text = clean_text(text)
                        
                        if (text and len(text) > 15 and 
                            not text.endswith(':') and
                            not any(word in text.lower()[:30] for word in [
                                'przejdź', 'zobacz', 'zapisz', 'aplikuj', 'oferty pracy',
                                'valid for', 'ważna jeszcze', 'company location', 'check how',
                                'location:', 'working hours:', 'type of project:', 'type of employment'
                            ]) and
                            not re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+ \d+', text)):  # Not an address
                            description_parts.append(text)
        
        if description_parts:
            description = ' '.join(description_parts)
            description = self._remove_unwanted_text(description)
            description = re.sub(r'\b(valid for|ważna jeszcze|ważna|Model of payment|System wynagrodzeń).*?\)', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\b(Location:|Working hours:|Type of project:|Type of employment|Specializations?:|języki?:).*?(?=\n|$)', '', description, flags=re.IGNORECASE | re.MULTILINE)
            description = re.sub(r'\b(contract of employment|umowa o pracę|kontrakt B2B|umowa zlecenie).*?(?=\n|$)', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\b(junior specialist|młodszy specjalista|specialist).*?\(Junior\)', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\b(Робота для іноземців|Запрошуємо працівників з України)', '', description, flags=re.IGNORECASE)
            description = re.sub(r'[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+ \d+[a-z]?[,]? [A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+.*?\([^)]+\)', '', description)
            description = re.sub(r'\s+', ' ', description).strip()
            
            return description
        
        return ""

    def _extract_technologies_from_section(self, soup: BeautifulSoup) -> str:
        """Extract technologies only from the technologies section."""
        tech_section = soup.find('section', {'data-test': 'section-technologies'})
        if not tech_section:
            return ""

        excluded_patterns = [
            'technologie u pracodawcy', 'technologie', 'technologies we use', 'technologies',
            'system operacyjny', 'operating system', 'wymagane', 'required', 'expected',
            'mile widziane', 'optional', 'preferred', 'technologie, których używamy'
        ]
        
        tech_names = []
        
        tech_items = tech_section.find_all(['li', 'span', 'div'], {
            'data-test': lambda x: x and ('technologies' in str(x).lower() or 'technology' in str(x).lower())
        })
        
        for item in tech_items:
            text = clean_text(item.get_text())
            if not text or len(text) < 2 or len(text) > 50:
                continue
            
            text_lower = text.lower().strip()
            if any(pattern in text_lower for pattern in excluded_patterns):
                continue
            
            if text.endswith(':') or text.endswith('：'):
                continue
                
            tech_names.append(text)

        os_section = tech_section.find('div', {'data-test': 'section-technologies-os'})
        if os_section:
            os_icons = os_section.find_all('svg', {'data-test': 'icon-technologies-os'})
            for icon in os_icons:
                defs = icon.find('defs')
                if defs:
                    mask_elem = defs.find('mask', id=True)
                    if mask_elem:
                        mask_id = mask_elem.get('id', '')
                        # Extract OS name from mask ID like "gp_system_Windows" -> "Windows"
                        if 'system_' in mask_id:
                            os_name = mask_id.split('system_')[-1]
                            if os_name and os_name.lower() not in [t.lower() for t in tech_names]:
                                tech_names.append(os_name)
                    
                    img_elem = defs.find('image', {'xlink:href': True})
                    if img_elem:
                        href = img_elem.get('xlink:href', '')
                        # Extract from URL like ".../operating-systems/windows.png" -> "Windows"
                        if 'operating-systems/' in href:
                            os_name = href.split('operating-systems/')[-1].replace('.png', '').capitalize()
                            if os_name and os_name.lower() not in [t.lower() for t in tech_names]:
                                tech_names.append(os_name)
                
                img_elem = icon.find('image', {'xlink:href': True})
                if img_elem:
                    href = img_elem.get('xlink:href', '')
                    if 'operating-systems/' in href:
                        os_name = href.split('operating-systems/')[-1].replace('.png', '').capitalize()
                        if os_name and os_name.lower() not in [t.lower() for t in tech_names]:
                            tech_names.append(os_name)

        # Remove duplicates while preserving order
        seen = set()
        unique_techs = []
        for tech in tech_names:
            tech_lower = tech.lower().strip()
            if tech_lower not in seen and tech_lower:
                seen.add(tech_lower)
                unique_techs.append(tech.strip())
        
        return ", ".join(unique_techs) if unique_techs else ""

    def _parse_salary_number(self, text: str) -> float:
        """Parse salary number, handling spaces as thousand separators and commas as decimal separators."""
        text = text.replace('\xa0', '').replace(' ', '')
        text = text.replace(',', '.')
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _extract_salary(self, soup: BeautifulSoup, description: str) -> dict[str, Any]:
        """Extract salary information from offer page"""
        salary_info = {'salary_min': None, 'salary_max': None, 'salary_period': None}
        
        salary_section = soup.find('div', {'data-test': 'section-salary'})
        if salary_section:
            first_salary_block = salary_section.find('div', {'data-test': 'section-salaryPerContractType'})
            if first_salary_block:
                earning_elem = first_salary_block.find('div', {'data-test': 'text-earningAmount'})
                if earning_elem:
                    earning_text = earning_elem.get_text(strip=True)
                    earning_text = earning_text.replace('\xa0', ' ')
                    
                    # Extract numbers - can be range like "5 000" or "35,00 – 50,00" or "6 300 – 8 700"
                    # Pattern: number (with spaces as thousand separators), optional comma/dot and decimals, separator, second number
                    # Handle both "5 000" (space as thousand separator) and "35,00" (comma as decimal)
                    range_pattern = r'(\d+(?:\s+\d{3})*(?:[,\.]\d+)?)\s*[–\-]\s*(\d+(?:\s+\d{3})*(?:[,\.]\d+)?)'
                    match = re.search(range_pattern, earning_text)
                    if match:
                        min_val = self._parse_salary_number(match.group(1))
                        max_val = self._parse_salary_number(match.group(2))
                        salary_info['salary_min'] = min_val
                        salary_info['salary_max'] = max_val
                    else:
                        # Single value
                        single_pattern = r'(\d+(?:\s+\d{3})*(?:[,\.]\d+)?)'
                        match = re.search(single_pattern, earning_text)
                        if match:
                            val = self._parse_salary_number(match.group(1))
                            salary_info['salary_min'] = val
                            salary_info['salary_max'] = val
                
                period_span = first_salary_block.find('span', class_=lambda x: x and 'i1jwft4m' in str(x))
                if period_span:
                    period_text = period_span.get_text(strip=True).lower()
                    if '/mth' in period_text or 'mth.' in period_text or 'miesięcznie' in period_text or 'mies.' in period_text or 'month' in period_text or '/mies' in period_text:
                        salary_info['salary_period'] = 'month'
                    elif '/h' in period_text or '/godz' in period_text or 'godzin' in period_text or 'hour' in period_text or 'godzinowa' in period_text or '/ godz' in period_text:
                        salary_info['salary_period'] = 'hour'
                    elif '/day' in period_text or '/dzień' in period_text or 'dniówka' in period_text:
                        salary_info['salary_period'] = 'day'
            
            if not salary_info.get('salary_period'):
                salary_text = salary_section.get_text().lower()
                if '/mth' in salary_text or 'mth.' in salary_text or 'miesięcznie' in salary_text or 'mies.' in salary_text or 'month' in salary_text or '/mies' in salary_text:
                    salary_info['salary_period'] = 'month'
                elif '/h' in salary_text or '/godz' in salary_text or 'godzin' in salary_text or 'hour' in salary_text or 'godzinowa' in salary_text or '/ godz' in salary_text:
                    salary_info['salary_period'] = 'hour'
                elif '/day' in salary_text or '/dzień' in salary_text or 'dniówka' in salary_text:
                    salary_info['salary_period'] = 'day'
                else:
                    if salary_info.get('salary_min'):
                        salary_info['salary_period'] = 'month'
        
        if not salary_info.get('salary_min'):
            salary_info = extract_salary(description)
        
        if salary_info.get('salary_min') and not salary_info.get('salary_period'):
            body_text = soup.get_text().lower()
            if any(indicator in body_text for indicator in ['/h', '/godz', 'godzin', 'na godzinę', 'za godzinę', '/ godz']):
                salary_info['salary_period'] = 'hour'
            elif any(indicator in body_text for indicator in ['/day', '/dzień', 'dniówka']):
                salary_info['salary_period'] = 'day'
            else:
                salary_info['salary_period'] = 'month'

        return salary_info

    def _extract_work_type(self, soup: BeautifulSoup, description: str) -> str:
        """Extract work type from offer page"""
        work_mode_elements = soup.find_all('li', {
            'data-test': lambda x: x and 'work-modes' in str(x).lower()
        })
        
        for elem in work_mode_elements:
            badge_title = elem.find('div', {'data-test': 'offer-badge-title'})
            if badge_title:
                work_mode_text = badge_title.get_text(strip=True).lower()
                
                # Map to our work types
                if 'hybrid' in work_mode_text or 'hybrydowa' in work_mode_text:
                    return 'hybrid'
                elif 'remote' in work_mode_text or 'zdalna' in work_mode_text or 'zdalnie' in work_mode_text:
                    return 'remote'
                elif 'on-site' in work_mode_text or 'stacjonarna' in work_mode_text or 'stacjonarnie' in work_mode_text:
                    return 'on-site'

        return ""

    def parse_offer(self, url: str) -> dict[str, Any] | None:
        """
        Parse single job offer page.
        """
        soup = self._get_page(url)
        if not soup:
            return None

        try:
            title = ""
            title_elem = soup.find('h1', {'data-test': 'text-positionName'})
            if title_elem:
                title = clean_text(title_elem.get_text())

            company = self._extract_company(soup)

            location = self._extract_location(soup)

            description = self._extract_description(soup)

            technologies = self._extract_technologies_from_section(soup)

            salary_info = self._extract_salary(soup, description)
            salary_min = salary_info.get('salary_min')
            salary_max = salary_info.get('salary_max')
            salary_period = salary_info.get('salary_period')

            work_type = self._extract_work_type(soup, description)

            contract_type = ""
            contract_elem = soup.find('li', {'data-test': 'sections-benefit-contracts'})
            if contract_elem:
                badge_title = contract_elem.find('div', {'data-test': 'offer-badge-title'})
                if badge_title:
                    contract_text = badge_title.get_text(strip=True).lower()
                    if 'b2b' in contract_text or 'kontrakt b2b' in contract_text:
                        contract_type = 'B2B'
                    elif 'contract of employment' in contract_text or 'umowa o pracę' in contract_text or 'uop' in contract_text:
                        contract_type = 'UoP'
                    elif 'contract of mandate' in contract_text or 'umowa zlecenie' in contract_text or 'uz' in contract_text:
                        contract_type = 'UZ'
                    elif 'contract for specific work' in contract_text or 'umowa o dzieło' in contract_text or 'uod' in contract_text:
                        contract_type = 'UoD'
                    elif 'staż' in contract_text or 'praktyki' in contract_text or 'internship' in contract_text:
                        contract_type = 'Staż/Praktyki'
            
            if not contract_type:
                description_lower = description.lower()
                for ct, keywords in CONTRACT_TYPE_KEYWORDS.items():
                    if any(kw in description_lower for kw in keywords):
                        contract_type = ct
                        break

            employment_type = ""
            schedule_elem = soup.find('li', {'data-test': 'sections-benefit-work-schedule'})
            if schedule_elem:
                badge_title = schedule_elem.find('div', {'data-test': 'offer-badge-title'})
                if badge_title:
                    schedule_text = badge_title.get_text(strip=True).lower()
                    if 'full-time' in schedule_text or 'pełny etat' in schedule_text:
                        employment_type = 'full-time'
                    elif 'part-time' in schedule_text or 'część etatu' in schedule_text or 'niepełny etat' in schedule_text:
                        employment_type = 'part-time'

            valid_until = None
            duration_elem = soup.find('div', {'data-test': 'section-duration-info'})
            if duration_elem:
                caption_paragraphs = duration_elem.find_all('p', class_=lambda x: x and 'caption' in str(x).lower())
                for caption_elem in caption_paragraphs:
                    date_text = caption_elem.get_text(strip=True)
                    # Remove parentheses if present
                    date_text = date_text.strip('()')
                    parsed_date = parse_valid_until_date(date_text)
                    if parsed_date:
                        valid_until = parsed_date
                        break

            offer_data = {
                'url': url,
                'title': title,
                'company': company,
                'location': location,
                'description': description if description else "",  # Full description
                'technologies': technologies,
                'salary_min': salary_min,
                'salary_max': salary_max,
                'salary_period': salary_period,
                'work_type': work_type,
                'contract_type': contract_type,
                'employment_type': employment_type,
                'valid_until': valid_until,
            }

            return offer_data

        except Exception as e:
            logger.error(f"Error parsing offer {url}: {e}")
            return None