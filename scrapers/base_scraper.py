"""Base scraper class for job portals."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all job portal scrapers."""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize scraper.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.source_name = self.__class__.__name__

    @abstractmethod
    def search_offers(self, keyword: str, max_pages: int = 5) -> list[str]:
        """
        Search for job offers and return list of URLs.

        Args:
            keyword: Search keyword
            max_pages: Maximum number of pages to scrape

        Returns:
            List of offer URLs
        """
        pass

    @abstractmethod
    def parse_offer(self, url: str) -> dict[str, Any] | None:
        """
        Parse single job offer page.

        Args:
            url: URL of the offer

        Returns:
            Dictionary with offer data or None if parsing failed
        """
        pass

    def scrape(self, keyword: str, max_pages: int = 5) -> list[dict[str, Any]]:
        """
        Scrape job offers for given keyword.

        Args:
            keyword: Search keyword
            max_pages: Maximum number of pages to scrape

        Returns:
            List of offer dictionaries
        """
        logger.info(f"Starting scrape for keyword: {keyword}")
        urls = self.search_offers(keyword, max_pages)
        logger.info(f"Found {len(urls)} offer URLs")

        offers = []
        for url in urls:
            try:
                offer = self.parse_offer(url)
                if offer:
                    offer['source'] = self.source_name
                    offers.append(offer)
            except Exception as e:
                logger.error(f"Error parsing offer {url}: {e}")

        logger.info(f"Successfully parsed {len(offers)} offers")
        return offers

    def scrape_page_by_page(self, keyword: str, max_pages: int = 5, db_manager=None, excluded_keywords: list[str] | None = None) -> int:
        """
        Scrape offers page by page (optional method for scrapers that support it).

        Args:
            keyword: Search keyword
            max_pages: Maximum number of pages to scrape
            db_manager: Database manager instance for saving offers
            excluded_keywords: List of keywords to exclude

        Returns:
            Number of saved offers

        Note:
            If not overridden, falls back to standard scrape() method
        """
        # Default implementation falls back to standard scrape
        excluded_keywords = excluded_keywords or []
        offers = self.scrape(keyword, max_pages)
        
        # Filter excluded keywords
        filtered_offers = []
        for offer in offers:
            title_lower = offer.get('title', '').lower()
            desc_lower = offer.get('description', '').lower()
            
            should_exclude = False
            for excluded in excluded_keywords:
                if excluded.lower() in title_lower or excluded.lower() in desc_lower:
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered_offers.append(offer)
        
        # Save to database
        saved_count = 0
        if db_manager:
            for offer in filtered_offers:
                if db_manager.insert_offer(offer):
                    saved_count += 1
        
        return saved_count