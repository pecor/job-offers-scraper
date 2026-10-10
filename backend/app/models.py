from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.database import Base


class CVDocument(Base):
    __tablename__ = "cv_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    # How the text was obtained: "pdf-text" (text layer) or "ocr" or "plain"
    extraction_method = Column(String, nullable=True)
    text_content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GeneratedMessage(Base):
    __tablename__ = "generated_messages"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, nullable=False, index=True)
    cv_id = Column(Integer, nullable=True)
    model = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    instructions = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobOffer(Base):
    __tablename__ = "job_offers"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    technologies = Column(String, nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_period = Column(String, nullable=True)
    work_type = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    valid_until = Column(Date, nullable=True)
    source = Column(String, nullable=False)
    seen = Column(Boolean, default=False, nullable=False, index=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
