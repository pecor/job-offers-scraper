import logging
import time
import requests
from typing import Any
from datetime import datetime

from scrapers.base_scraper import BaseScraper
from utils.utils import get_random_user_agent
from .config import API_BASE_URL, OFFER_BASE_URL, DEFAULT_PARAMS

logger = logging.getLogger(__name__)


class JustJoinItScraper(BaseScraper):
    """justjoin.it job portal scraper using API"""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize justjoin.it scraper.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8',
            'Origin': 'https://justjoin.it',
            'Referer': 'https://justjoin.it/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        })
        self.delay = config.get('delay', 0.5) if config else 0.5

    def _make_api_request(self, keyword: str, from_offset: int = 0, items_count: int = 100) -> dict[str, Any] | None:
        try:
            time.sleep(self.delay)
            
            params = DEFAULT_PARAMS.copy()
            params['from'] = from_offset
            params['itemsCount'] = items_count
            if keyword:
                keywords_list = [kw.strip() for kw in keyword.split(',') if kw.strip()]
                for idx, kw in enumerate(keywords_list):
                    params[f'keywords[{idx}]'] = kw
            
            response = self.session.get(API_BASE_URL, params=params, timeout=10)
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
            max_pages: Maximum number of pages to scrape (each page = 100 items)
            
        Returns:
            List of offer URLs
        """
        urls = []
        items_per_page = 100
        total_items = max_pages * items_per_page
        
        for offset in range(0, total_items, items_per_page):
            page_num = (offset // items_per_page) + 1
            logger.info(f"Scraping page {page_num} (offset {offset})")
            
            data = self._make_api_request(keyword, from_offset=offset, items_count=items_per_page)
            if not data or 'data' not in data:
                logger.info(f"No more offers found at offset {offset}")
                break
            
            offers = data.get('data', [])
            if not offers:
                logger.info(f"No offers in response at offset {offset}")
                break
            
            for offer in offers:
                slug = offer.get('slug')
                if slug:
                    url = f"{OFFER_BASE_URL}/{slug}"
                    if url not in urls:
                        urls.append(url)
            
            logger.info(f"Found {len(offers)} offers on page {page_num}")
            
            # If we got less than items_per_page, we've reached the end
            if len(offers) < items_per_page:
                break
        
        return urls

    def parse_offer(self, url: str) -> dict[str, Any] | None:
        # Extract slug from URL
        slug = url.replace(f"{OFFER_BASE_URL}/", "")
        if not slug:
            logger.error(f"Invalid URL format: {url}")
            return None
        
        data = self._make_api_request("", from_offset=0, items_count=1000)
        if not data or 'data' not in data:
            logger.error(f"Could not fetch offer data for {url}")
            return None
        
        offer_data = None
        for offer in data.get('data', []):
            if offer.get('slug') == slug:
                offer_data = offer
                break
        
        if not offer_data:
            logger.warning(f"Offer not found in API response: {slug}")
            return None
        
        return self._parse_api_offer(offer_data, url)

    def _parse_api_offer(self, offer_data: dict[str, Any], url: str) -> dict[str, Any]:
        salary_min = None
        salary_max = None
        salary_period = None
        
        employment_types = offer_data.get('employmentTypes', [])
        if employment_types:
            emp_type = employment_types[0]
            salary_min = emp_type.get('fromPln') or emp_type.get('from')
            salary_max = emp_type.get('toPln') or emp_type.get('to')
            unit = emp_type.get('unit', 'month')
            if unit == 'month':
                salary_period = 'month'
            elif unit == 'hour':
                salary_period = 'hour'
            elif unit == 'day':
                salary_period = 'day'
            else:
                salary_period = 'month'  # default
        
        required_skills = offer_data.get('requiredSkills', []) or []
        nice_to_have_skills = offer_data.get('niceToHaveSkills', []) or []
        all_skills = required_skills + nice_to_have_skills
        technologies = ", ".join(all_skills) if all_skills else ""
        
        workplace_type = offer_data.get('workplaceType', '').lower()
        work_type = ""
        if 'remote' in workplace_type:
            work_type = 'remote'
        elif 'hybrid' in workplace_type:
            work_type = 'hybrid'
        elif 'office' in workplace_type or 'on-site' in workplace_type:
            work_type = 'on-site'
        
        # Extract contract type (not directly available in API, might need to parse from description)
        contract_type = ""
        
        working_time = offer_data.get('workingTime', '').lower()
        employment_type = ""
        if 'full' in working_time:
            employment_type = 'full-time'
        elif 'part' in working_time:
            employment_type = 'part-time'
        
        city = offer_data.get('city', '')
        street = offer_data.get('street', '')
        location = city
        if street:
            location = f"{street}, {city}" if city else street
        
        valid_until = None
        expired_at = offer_data.get('expiredAt')
        if expired_at:
            try:
                valid_until = datetime.fromisoformat(expired_at.replace('Z', '+00:00')).date()
            except Exception as e:
                logger.debug(f"Could not parse expiredAt: {expired_at}, error: {e}")
        
        # Description created by parsing available fields
        description_parts = []
        if offer_data.get('title'):
            description_parts.append(f"Position: {offer_data.get('title')}")
        if technologies:
            description_parts.append(f"Technologies: {technologies}")
        if offer_data.get('experienceLevel'):
            description_parts.append(f"Experience level: {offer_data.get('experienceLevel')}")
        
        description = " | ".join(description_parts)
        
        return {
            'url': url,
            'title': offer_data.get('title', ''),
            'company': offer_data.get('companyName', ''),
            'location': location,
            'description': description,
            'technologies': technologies,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_period': salary_period,
            'work_type': work_type,
            'contract_type': contract_type,
            'employment_type': employment_type,
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
        items_per_page = 100
        total_items = max_pages * items_per_page
        
        for offset in range(0, total_items, items_per_page):
            page_num = (offset // items_per_page) + 1
            logger.info(f"Scraping page {page_num} (offset {offset})")
            
            data = self._make_api_request(keyword, from_offset=offset, items_count=items_per_page)
            if not data or 'data' not in data:
                logger.info(f"No more offers found at offset {offset}")
                break
            
            offers = data.get('data', [])
            if not offers:
                logger.info(f"No offers in response at offset {offset}")
                break
            
            logger.info(f"Found {len(offers)} offers on page {page_num}")
            
            for offer_data in offers:
                slug = offer_data.get('slug')
                if not slug:
                    continue
                
                url = f"{OFFER_BASE_URL}/{slug}"
                
                try:
                    offer = self._parse_api_offer(offer_data, url)
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
                    
                    if db_manager and db_manager.insert_offer(offer):
                        saved_count += 1
                        logger.info(f"Saved: {offer.get('title', 'Unknown')}")
                
                except Exception as e:
                    logger.error(f"Error processing offer {url}: {e}")
            
            # If we got less than items_per_page, we've reached the end
            if len(offers) < items_per_page:
                break
        
        return saved_count
