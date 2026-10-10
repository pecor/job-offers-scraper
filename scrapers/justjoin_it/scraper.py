import logging
import time
import requests
from typing import Any
from datetime import datetime

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from utils.utils import get_random_user_agent
from .config import API_BASE_URL, OFFER_BASE_URL, DEFAULT_PARAMS

logger = logging.getLogger(__name__)


class JustJoinItScraper(BaseScraper):
    """justjoin.it job portal scraper using public candidate API (via site reverse proxy)"""

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
            'Referer': 'https://justjoin.it/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        self.delay = config.get('delay', 0.5) if config else 0.5

    def _make_listing_request(self, keyword: str, from_offset: int = 0, items_count: int = 100) -> dict[str, Any] | None:
        """Fetch offers listing page. Keyword filters via repeated `keywords` params."""
        try:
            time.sleep(self.delay)

            params = DEFAULT_PARAMS.copy()
            params['from'] = from_offset
            params['itemsCount'] = items_count
            # keywords must be passed as repeated query params: keywords=a&keywords=b
            keywords_list = [kw.strip() for kw in keyword.split(',') if kw.strip()]
            if keywords_list:
                params['keywords'] = keywords_list
                params['keywordType'] = 'any'

            response = self.session.get(API_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching listing API: {e}")
            return None

    def _make_detail_request(self, slug: str) -> dict[str, Any] | None:
        """Fetch single offer details (includes full description)."""
        try:
            time.sleep(self.delay)
            response = self.session.get(f"{API_BASE_URL}/{slug}", params={'currency': 'pln'}, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching offer details {slug}: {e}")
            return None

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Strip HTML tags from offer body."""
        if not html:
            return ''
        soup = BeautifulSoup(html, 'lxml')
        return soup.get_text(separator='\n', strip=True)

    def search_offers(self, keyword: str, max_pages: int = 5) -> list[str]:
        """
        Search for job offers using API and return list of URLs.

        Args:
            keyword: Search keyword (comma-separated keywords allowed)
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

            data = self._make_listing_request(keyword, from_offset=offset, items_count=items_per_page)
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
        """
        Parse single job offer by fetching its details endpoint.

        Args:
            url: URL of the offer

        Returns:
            Dictionary with offer data or None if parsing failed
        """
        slug = url.replace(f"{OFFER_BASE_URL}/", "")
        if not slug:
            logger.error(f"Invalid URL format: {url}")
            return None

        data = self._make_detail_request(slug)
        if not data or not data.get('slug'):
            logger.warning(f"Could not fetch offer data for {url}")
            return None

        return self._parse_api_offer(data)

    def _pick_salary(self, employment_types: list[dict[str, Any]]) -> tuple[float | None, float | None, str | None]:
        """Pick PLN salary range when available, fall back to first entry."""
        salary_min = None
        salary_max = None
        salary_period = None

        chosen = None
        for emp_type in employment_types or []:
            if str(emp_type.get('currency', '')).lower() == 'pln':
                chosen = emp_type
                break
        if chosen is None and employment_types:
            chosen = employment_types[0]

        if chosen:
            salary_min = chosen.get('from')
            salary_max = chosen.get('to')
            unit = str(chosen.get('unit', 'month')).lower()
            salary_period = unit if unit in ('month', 'hour', 'day') else 'month'

        return salary_min, salary_max, salary_period

    def _parse_api_offer(self, offer_data: dict[str, Any], url: str | None = None) -> dict[str, Any]:
        url = url or offer_data.get('url') or f"{OFFER_BASE_URL}/{offer_data.get('slug', '')}"

        salary_min, salary_max, salary_period = self._pick_salary(offer_data.get('employmentTypes', []))

        required_skills = [s.get('name') for s in (offer_data.get('requiredSkills') or []) if s.get('name')]
        nice_to_have_skills = [s.get('name') for s in (offer_data.get('niceToHaveSkills') or []) if s.get('name')]
        all_skills = required_skills + nice_to_have_skills
        technologies = ", ".join(all_skills)

        workplace_type = str(offer_data.get('workplaceType', '')).lower()
        work_type = ''
        if 'remote' in workplace_type:
            work_type = 'remote'
        elif 'hybrid' in workplace_type:
            work_type = 'hybrid'
        elif 'office' in workplace_type or 'on-site' in workplace_type:
            work_type = 'on-site'

        # Contract type (b2b / permanent etc.) is derived from first employment type
        contract_type = ''
        employment_types = offer_data.get('employmentTypes') or []
        if employment_types:
            contract_type = str(employment_types[0].get('type', ''))

        working_time = str(offer_data.get('workingTime', '')).lower()
        employment_type = ''
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

        description = self._html_to_text(offer_data.get('body', ''))

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

    def scrape_page_by_page(self, keyword: str, max_pages: int, db_manager=None, excluded_keywords: list[str] | None = None, search_in_description: bool = False) -> int:
        """
        Scrape offers page by page using API, parsing and saving each offer immediately.

        Args:
            keyword: Search keyword
            max_pages: Maximum number of pages to scrape
            db_manager: Database manager instance for saving offers
            excluded_keywords: List of keywords to exclude
            search_in_description: If True, also search excluded keywords in description

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

            data = self._make_listing_request(keyword, from_offset=offset, items_count=items_per_page)
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

                try:
                    offer = self.parse_offer(f"{OFFER_BASE_URL}/{slug}")
                    if not offer:
                        continue

                    offer['source'] = self.source_name

                    # Filter excluded keywords
                    title_lower = offer.get('title', '').lower()
                    desc_lower = offer.get('description', '').lower()

                    should_exclude = False
                    for excluded in excluded_keywords:
                        if excluded.lower() in title_lower or (search_in_description and excluded.lower() in desc_lower):
                            should_exclude = True
                            logger.debug(f"Excluding offer: {offer.get('title')} (matched: {excluded})")
                            break

                    if should_exclude:
                        continue

                    if db_manager and db_manager.insert_offer(offer):
                        saved_count += 1
                        logger.info(f"Saved: {offer.get('title', 'Unknown')}")

                except Exception as e:
                    logger.error(f"Error processing offer {slug}: {e}")

            # If we got less than items_per_page, we've reached the end
            if len(offers) < items_per_page:
                break

        return saved_count
