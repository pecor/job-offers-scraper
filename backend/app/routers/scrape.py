import logging
import threading
from typing import Dict
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.schemas import Config

from scrapers.pracuj_pl import PracujPlScraper
from scrapers.justjoin_it import JustJoinItScraper
from scrapers.nofluffjobs import NoFluffJobsScraper
from app.database import SessionLocal
from app.db_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)
router = APIRouter()

scraping_results: dict[str, Dict] = {}


def run_scraper_for_source(source_name: str, config: dict, db_session, task_id: str):
    saved_count = 0
    try:
        scraper_config = {
            'delay': config.get('delay', 1.0),
        }
        
        if source_name == 'pracuj_pl':
            scraper_config['pracuj_pl_domain'] = config.get('pracuj_pl_domain', 'it')
            scraper = PracujPlScraper(scraper_config)
        elif source_name == 'justjoin_it':
            scraper = JustJoinItScraper(scraper_config)
        elif source_name == 'nofluffjobs':
            scraper = NoFluffJobsScraper(scraper_config)
        else:
            logger.error(f"Unknown source: {source_name}")
            return 0

        keyword = config.get('search_keyword', 'junior')
        max_pages = config.get('max_pages', 5)
        excluded_keywords = config.get('excluded_keywords', [])

        # Create database adapter
        db_adapter = DatabaseAdapter(db_session)

        if hasattr(scraper, 'scrape_page_by_page'):
            # Use page-by-page scraping
            saved_count = scraper.scrape_page_by_page(
                keyword, max_pages, db_adapter, excluded_keywords
            )
            logger.info(f"{source_name} completed! Saved: {saved_count} new offers")
        else:
            # Fallback to standard scraping
            offers = scraper.scrape(keyword, max_pages)
            logger.info(f"{source_name} found {len(offers)} offers")

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

            logger.info(f"{source_name} after filtering: {len(filtered_offers)} offers")

            # Save to database
            saved_count = 0
            for offer in filtered_offers:
                if db_adapter.insert_offer(offer):
                    saved_count += 1
                    logger.info(f"Saved: {offer.get('title', 'Unknown')}")

            logger.info(f"{source_name} completed! Found: {len(offers)}, Saved: {saved_count} new offers")
    except Exception as e:
        logger.error(f"Error scraping {source_name}: {e}", exc_info=True)
    finally:
        db_session.close()
        # Update results
        if task_id in scraping_results:
            scraping_results[task_id]['results'][source_name] = saved_count
    return saved_count


def run_scrapers_task(config: Config, task_id: str):
    sources = config.sources
    if not sources:
        logger.error("No sources configured")
        return

    logger.info(f"Starting scrapers for keyword: {config.search_keyword}, sources: {sources}")

    # Initialize results
    scraping_results[task_id] = {
        'status': 'running',
        'started_at': datetime.now().isoformat(),
        'results': {source: 0 for source in sources}
    }

    config_dict = config.model_dump()
    
    # Run each scraper in a separate thread/process
    threads = []
    for source in sources:
        db_session = SessionLocal()
        thread = threading.Thread(
            target=run_scraper_for_source,
            args=(source, config_dict, db_session, task_id),
            daemon=False
        )
        thread.start()
        threads.append(thread)
        logger.info(f"Started scraper thread for {source}")

    for thread in threads:
        thread.join()

    # Mark as completed
    scraping_results[task_id]['status'] = 'completed'
    scraping_results[task_id]['completed_at'] = datetime.now().isoformat()
    
    logger.info("All scrapers completed!")


@router.post("/scrape/start")
async def start_scrape(config: Config, background_tasks: BackgroundTasks):
    if not config.sources:
        raise HTTPException(status_code=400, detail="No sources selected")
    
    import uuid
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_scrapers_task, config, task_id)
    return {"message": "Scraping started", "sources": config.sources, "task_id": task_id}


@router.get("/scrape/status/{task_id}")
async def get_scrape_status(task_id: str):
    """Get scraping status and results."""
    if task_id not in scraping_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = scraping_results[task_id]
    return result
