"""Main entry point for job offers scraper."""

import argparse
import logging
import sys

from nicegui import ui
from gui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_cli():
    """Run scraper in CLI mode."""
    from config.config_manager import ConfigManager
    from database.db_manager import DatabaseManager
    from scrapers.pracuj_pl import PracujPlScraper

    config = ConfigManager()
    db = DatabaseManager()

    keyword = config.get('search_keyword', 'junior')
    max_pages = config.get('max_pages', 5)
    delay = config.get('delay', 1.0)
    domain = config.get('pracuj_pl_domain', 'it')
    excluded_keywords = config.get('excluded_keywords', [])

    logger.info(f"Starting scraper for keyword: {keyword} on domain: {domain}")

    scraper = PracujPlScraper({
        'delay': delay,
        'pracuj_pl_domain': domain
    })
    
    # Use page-by-page scraping if available
    if hasattr(scraper, 'scrape_page_by_page'):
        saved_count = scraper.scrape_page_by_page(keyword, max_pages, db, excluded_keywords)
        logger.info(f"Scraping completed! Saved: {saved_count} new offers")
    else:
        # Fallback to standard scraping
        offers = scraper.scrape(keyword, max_pages)
        logger.info(f"Found {len(offers)} offers")

        # Filter excluded keywords
        filtered_offers = []
        for offer in offers:
            title_lower = offer.get('title', '').lower()
            desc_lower = offer.get('description', '').lower()

            should_exclude = False
            for excluded in excluded_keywords:
                if excluded.lower() in title_lower or excluded.lower() in desc_lower:
                    should_exclude = True
                    logger.debug(f"Excluding offer: {offer.get('title')} (matched: {excluded})")
                    break

            if not should_exclude:
                filtered_offers.append(offer)

        logger.info(f"After filtering: {len(filtered_offers)} offers")

        # Save to database
        saved_count = 0
        for offer in filtered_offers:
            if db.insert_offer(offer):
                saved_count += 1
                logger.info(f"Saved: {offer.get('title', 'Unknown')}")

        logger.info(f"Scraping completed! Found: {len(offers)}, Saved: {saved_count} new offers")


def run_gui():
    """Run scraper in GUI mode"""
    try:
        MainWindow()
        
        ui.run(host='0.0.0.0', port=8080, title='Job offers scraper', show=False)
    except ImportError:
        logger.error("GUI mode requires nicegui. Use --cli flag or install nicegui.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting GUI: {e}")
        sys.exit(1)


def main():
    """Main function to start the application."""
    parser = argparse.ArgumentParser(description='Job Offers Scraper')
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Run in CLI mode (no GUI)'
    )
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Run in GUI mode (default if available)'
    )

    args = parser.parse_args()

    if args.cli:
        run_cli()
    else:
        # Try GUI first, fallback to CLI if GUI unavailable
        try:
            run_gui()
        except (ImportError, Exception) as e:
            logger.warning(f"GUI mode unavailable: {e}. Falling back to CLI mode.")
            run_cli()


if __name__ in {"__main__", "__mp_main__"}:
    main()