import logging
from typing import Any
from sqlalchemy.orm import Session
from app.models import JobOffer

logger = logging.getLogger(__name__)


class DatabaseAdapter:    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def offer_exists(self, url: str) -> bool:
        existing = self.db_session.query(JobOffer).filter(JobOffer.url == url).first()
        return existing is not None
    
    def insert_offer(self, offer_data: dict[str, Any]) -> bool:
        url = offer_data.get('url')
        if not url:
            logger.error("Cannot insert offer without URL")
            return False

        if self.offer_exists(url):
            logger.debug(f"Offer already exists: {url}")
            return False

        try:
            offer = JobOffer(
                url=offer_data.get('url'),
                title=offer_data.get('title', ''),
                company=offer_data.get('company'),
                location=offer_data.get('location'),
                description=offer_data.get('description'),
                technologies=offer_data.get('technologies'),
                salary_min=offer_data.get('salary_min'),
                salary_max=offer_data.get('salary_max'),
                salary_period=offer_data.get('salary_period'),
                work_type=offer_data.get('work_type'),
                contract_type=offer_data.get('contract_type'),
                employment_type=offer_data.get('employment_type'),
                valid_until=offer_data.get('valid_until'),
                source=offer_data.get('source'),
            )
            self.db_session.add(offer)
            self.db_session.commit()
            logger.info(f"Inserted offer: {offer_data.get('title', url)}")
            return True
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error inserting offer: {e}")
            return False
