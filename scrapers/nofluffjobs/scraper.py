import logging
import time
import requests
from typing import Any
from datetime import datetime, timedelta

from scrapers.base_scraper import BaseScraper
from utils.utils import get_random_user_agent

logger = logging.getLogger(__name__)

API_BASE_URL = "https://nofluffjobs.com/api/search/posting"
OFFER_BASE_URL = "https://nofluffjobs.com/pl/job"


class NoFluffJobsScraper(BaseScraper):
    """nofluffjobs.com job portal scraper using API"""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize nofluffjobs.com scraper.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)
        self.source_name = 'nofluffjobs'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
            'Content-Type': 'application/infiniteSearch+json',
            'Origin': 'https://nofluffjobs.com',
            'Referer': 'https://nofluffjobs.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        self.delay = config.get('delay', 0.5) if config else 0.5

    def _make_api_request(self, keyword: str, page_to: int = 1, page_size: int = 100) -> dict[str, Any] | None:
        """
        Make API request to nofluffjobs.com.

        Args:
            keyword: Search keyword
            page_to: Page number (1-based)
            page_size: Number of items per page

        Returns:
            API response as dictionary or None if error
        """
        try:
            time.sleep(self.delay)
            
            # Query parameters
            params = {
                'withSalaryMatch': 'true',
                'pageTo': str(page_to),
                'pageSize': str(page_size),
                'salaryCurrency': 'PLN',
                'salaryPeriod': 'month',
                'region': 'pl',
                'language': 'pl-PL',
            }
            
            # Request body
            body = {
                'criteria': f"requirement='{keyword}'" if keyword else '',
                'url': {'searchParam': keyword} if keyword else {},
                'rawSearch': f"'{keyword}' requirement='{keyword}'" if keyword else '',
                'pageSize': page_size,
                'withSalaryMatch': True,
            }
            
            response = self.session.post(
                API_BASE_URL,
                params=params,
                json=body,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching API: {e}")
            return None

    def search_offers(self, keyword: str, max_pages: int = 5) -> list[str]:
        """
        Search for job offers using API and return list of URLs.
        
        Args:
            keyword: Search keyword
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of offer URLs
        """
        urls = []
        
        for page in range(1, max_pages + 1):
            logger.info(f"Scraping page {page}")
            
            data = self._make_api_request(keyword, page_to=page, page_size=100)
            if not data or 'postings' not in data:
                logger.info(f"No more offers found on page {page}")
                break
            
            postings = data.get('postings', [])
            if not postings:
                logger.info(f"No offers in response on page {page}")
                break
            
            for posting in postings:
                url_slug = posting.get('url')
                if url_slug:
                    full_url = f"{OFFER_BASE_URL}/{url_slug}"
                    if full_url not in urls:
                        urls.append(full_url)
            
            logger.info(f"Found {len(postings)} offers on page {page}")
            
            # If we got less than page_size, we've reached the end
            if len(postings) < 100:
                break
        
        return urls

    def parse_offer(self, url: str) -> dict[str, Any] | None:
        """
        Parse single job offer from API response.
        
        Note: This method searches through API responses to find the offer.
        For better performance, use scrape_page_by_page instead.
        
        Args:
            url: URL of the offer
            
        Returns:
            Dictionary with offer data or None if parsing failed
        """
        # Extract slug from URL
        slug = url.replace(f"{OFFER_BASE_URL}/", "")
        if not slug:
            logger.error(f"Invalid URL format: {url}")
            return None
        
        # Search through pages to find the offer
        for page in range(1, 6):  # Search up to 5 pages
            data = self._make_api_request("", page_to=page, page_size=100)
            if not data or 'postings' not in data:
                break
            
            for posting in data.get('postings', []):
                if posting.get('url') == slug:
                    return self._parse_api_posting(posting, url)
        
        logger.warning(f"Offer not found in API response: {slug}")
        return None

    def _parse_api_posting(self, posting: dict[str, Any], url: str) -> dict[str, Any]:
        """
        Parse API posting data into offer dictionary.
        
        Args:
            posting: Posting data from API
            url: Full URL of the offer
            
        Returns:
            Dictionary with offer data
        """
        # Extract location
        location_parts = []
        places = posting.get('location', {}).get('places', [])
        if places:
            # Prefer city over Remote, prefer first non-provinceOnly place
            for place in places:
                if place.get('provinceOnly'):
                    continue
                city = place.get('city')
                if city and city != 'Remote':
                    location_parts.append(city)
                    break
            # If no city found, check for Remote
            if not location_parts:
                for place in places:
                    if place.get('city') == 'Remote':
                        location_parts.append('Remote')
                        break
        
        location = ', '.join(location_parts) if location_parts else None
        
        # Extract work type
        work_type = ""
        location_obj = posting.get('location', {})
        if location_obj.get('fullyRemote'):
            work_type = 'remote'
        elif location_obj.get('hybridDesc'):
            work_type = 'hybrid'
        else:
            work_type = 'on-site'
        
        # Extract salary
        salary_min = None
        salary_max = None
        salary_period = None
        contract_type = None
        
        salary = posting.get('salary')
        if salary:
            salary_min = salary.get('from')
            salary_max = salary.get('to')
            salary_type = salary.get('type', '').lower()
            if salary_type == 'b2b':
                contract_type = 'B2B'
            elif salary_type == 'uop':
                contract_type = 'UoP'
            elif salary_type == 'uz':
                contract_type = 'UZ'
            
            # Determine salary period from currency and type
            currency = salary.get('currency', 'PLN')
            # Default to month for PLN
            salary_period = 'month'
        
        # Extract technologies from tiles
        technologies = []
        tiles = posting.get('tiles', {})
        values = tiles.get('values', [])
        for tile in values:
            if tile.get('type') == 'requirement':
                tech = tile.get('value')
                if tech and tech not in technologies:
                    technologies.append(tech)
        
        technologies_str = ', '.join(technologies) if technologies else None
        
        # Extract valid_until from renewed timestamp
        valid_until = None
        renewed = posting.get('renewed')
        if renewed:
            try:
                # renewed is timestamp in milliseconds
                renewed_dt = datetime.fromtimestamp(renewed / 1000)
                # Add 30 days to renewed date as valid_until (typical job posting duration)
                valid_until = (renewed_dt + timedelta(days=30)).date()
            except Exception as e:
                logger.debug(f"Could not parse renewed timestamp: {renewed}, error: {e}")
        
        # Build description from available data
        description_parts = []
        if posting.get('category'):
            description_parts.append(f"Kategoria: {posting.get('category')}")
        if posting.get('seniority'):
            seniority_str = ', '.join(posting.get('seniority', []))
            description_parts.append(f"Poziom: {seniority_str}")
        if technologies:
            description_parts.append(f"Technologie: {', '.join(technologies)}")
        
        description = " | ".join(description_parts) if description_parts else None
        
        return {
            'url': url,
            'title': posting.get('title', ''),
            'company': posting.get('name', ''),
            'location': location,
            'description': description,
            'technologies': technologies_str,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_period': salary_period,
            'work_type': work_type,
            'contract_type': contract_type,
            'employment_type': None,  # Not available in API
            'valid_until': valid_until,
        }

    def scrape_page_by_page(self, keyword: str, max_pages: int, db_manager=None, excluded_keywords: list[str] | None = None) -> int:
        """
        Scrape offers page by page using API, parsing and saving each offer immediately.

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
        
        for page in range(1, max_pages + 1):
            logger.info(f"Scraping page {page}")
            
            data = self._make_api_request(keyword, page_to=page, page_size=100)
            if not data or 'postings' not in data:
                logger.info(f"No more offers found on page {page}")
                break
            
            postings = data.get('postings', [])
            if not postings:
                logger.info(f"No offers in response on page {page}")
                break
            
            logger.info(f"Found {len(postings)} offers on page {page}")
            
            for posting in postings:
                url_slug = posting.get('url')
                if not url_slug:
                    continue
                
                url = f"{OFFER_BASE_URL}/{url_slug}"
                
                try:
                    offer = self._parse_api_posting(posting, url)
                    if not offer:
                        continue
                    
                    offer['source'] = self.source_name
                    
                    # Filter excluded keywords
                    title_lower = offer.get('title', '').lower()
                    desc_lower = offer.get('description', '').lower()
                    tech_lower = offer.get('technologies', '').lower()
                    
                    should_exclude = False
                    for excluded in excluded_keywords:
                        if (excluded.lower() in title_lower or 
                            excluded.lower() in desc_lower or
                            excluded.lower() in tech_lower):
                            should_exclude = True
                            logger.debug(f"Excluding offer: {offer.get('title')} (matched: {excluded})")
                            break
                    
                    if should_exclude:
                        continue
                    
                    if db_manager and db_manager.insert_offer(offer):
                        saved_count += 1
                        logger.info(f"Saved: {offer.get('title', 'Unknown')}")
                
                except Exception as e:
                    logger.error(f"Error processing offer {url}: {e}")
            
            # If we got less than 100, we've reached the end
            if len(postings) < 100:
                break
        
        return saved_count
