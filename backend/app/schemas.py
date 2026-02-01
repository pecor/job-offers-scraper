from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class JobOfferBase(BaseModel):
    url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_period: Optional[str] = None
    work_type: Optional[str] = None
    contract_type: Optional[str] = None
    employment_type: Optional[str] = None
    valid_until: Optional[date] = None
    source: str


class JobOfferCreate(JobOfferBase):
    pass


class JobOffer(JobOfferBase):
    id: int
    seen: bool = False
    scraped_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ConfigBase(BaseModel):
    search_keyword: str = "junior"
    max_pages: int = 5
    delay: float = 1.0
    pracuj_pl_domain: str = "it"
    excluded_keywords: list[str] = []
    schedule: str = "daily"
    sources: list[str] = ["pracuj_pl"]


class Config(ConfigBase):
    pass
