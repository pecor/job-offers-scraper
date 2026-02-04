import logging
from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import JobOffer

logger = logging.getLogger(__name__)


class DatabaseAdapter:    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def offer_exists(self, url: str) -> bool:
        existing = self.db_session.query(JobOffer).filter(JobOffer.url == url).first()
        return existing is not None
    
    def offer_exists_by_company_title(self, company: str | None, title: str) -> bool:
        """
        Check if an offer with the same company and title already exists.
        Comparison is case-insensitive.
        
        Args:
            company: Company name (can be None)
            title: Job title
            
        Returns:
            True if duplicate exists, False otherwise
        """
        if not title:
            return False
        
        query = self.db_session.query(JobOffer).filter(
            func.lower(JobOffer.title) == title.lower()
        )
        if company:
            query = query.filter(func.lower(JobOffer.company) == company.lower())
        else:
            query = query.filter(JobOffer.company.is_(None))
        
        existing = query.first()
        return existing is not None
    
    def count_duplicates_by_company_title(self, company: str | None, title: str) -> int:
        """
        Count how many offers with the same company and title already exist.
        Comparison is case-insensitive.
        
        Args:
            company: Company name (can be None)
            title: Job title
            
        Returns:
            Number of existing duplicates
        """
        if not title:
            return 0
        
        query = self.db_session.query(JobOffer).filter(
            func.lower(JobOffer.title) == title.lower()
        )
        if company:
            query = query.filter(func.lower(JobOffer.company) == company.lower())
        else:
            query = query.filter(JobOffer.company.is_(None))
        
        return query.count()
    
    def insert_offer(self, offer_data: dict[str, Any], check_duplicates: bool = True) -> bool:
        url = offer_data.get('url')
        if not url:
            logger.error("Cannot insert offer without URL")
            return False

        # Check for duplicate URL
        if self.offer_exists(url):
            logger.debug(f"Offer already exists: {url}")
            return False

        # Check for duplicates by company + title if enabled
        if check_duplicates:
            company = offer_data.get('company')
            title = offer_data.get('title', '')
            duplicate_count = self.count_duplicates_by_company_title(company, title)
            
            if duplicate_count > 0:
                # If we already have an offer with the same company and title, don't add another one
                logger.debug(f"Skipping duplicate offer: {title} at {company} (already have {duplicate_count} duplicate(s))")
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
