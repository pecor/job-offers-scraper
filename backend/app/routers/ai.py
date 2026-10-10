"""AI endpoints: personalized application message generation."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import JobOffer, CVDocument, GeneratedMessage
from app.services.llm import (
    DEFAULT_SYSTEM_PROMPT,
    build_application_prompt,
    get_default_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    offer_id: int
    cv_text: str = ""
    cv_id: int | None = None
    instructions: str = ""
    system_prompt: str = ""  # empty = default prompt


class GenerateResponse(BaseModel):
    id: int
    message: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class PreviewRequest(BaseModel):
    offer_id: int
    cv_text: str = ""
    cv_id: int | None = None
    instructions: str = ""


class MessageInfo(BaseModel):
    id: int
    offer_id: int
    model: str
    message: str
    instructions: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: str | None


def _resolve_cv_text(request: GenerateRequest | PreviewRequest, db: Session) -> str:
    cv_text = request.cv_text.strip()
    if request.cv_id is not None:
        doc = db.query(CVDocument).filter(CVDocument.id == request.cv_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="CV document not found")
        cv_text = doc.text_content
    if not cv_text:
        raise HTTPException(status_code=400, detail="Provide cv_id or cv_text")
    return cv_text


@router.get("/ai/config")
async def ai_config():
    """Report LLM availability (no secrets)."""
    service = get_default_service()
    return {
        "configured": service.configured,
        "model": settings.LLM_MODEL,
        "base_url": settings.LLM_BASE_URL,
    }


@router.get("/ai/prompt")
async def get_system_prompt():
    """Return the default system prompt (editable on the client side)."""
    return {"system_prompt": DEFAULT_SYSTEM_PROMPT}


@router.post("/ai/preview")
async def preview_prompt(request: PreviewRequest, db: Session = Depends(get_db)):
    """Build and return the exact user prompt without calling the LLM."""
    offer = db.query(JobOffer).filter(JobOffer.id == request.offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    cv_text = _resolve_cv_text(request, db)

    prompt = build_application_prompt(
        offer={
            "title": offer.title,
            "company": offer.company,
            "location": offer.location,
            "technologies": offer.technologies,
            "salary_min": offer.salary_min,
            "salary_max": offer.salary_max,
            "salary_period": offer.salary_period,
            "description": offer.description,
        },
        cv_text=cv_text,
        instructions=request.instructions,
    )
    return {"user_prompt": prompt, "approx_chars": len(prompt)}


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_message(request: GenerateRequest, db: Session = Depends(get_db)):
    """Generate a personalized application message for a single offer.

    Pass either `cv_id` (uploaded CV) or `cv_text` (inline text).
    The result is sanitized (AI-tell characters removed) and stored in the database.
    """
    offer = db.query(JobOffer).filter(JobOffer.id == request.offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    cv_text = _resolve_cv_text(request, db)

    service = get_default_service()
    if not service.configured:
        raise HTTPException(status_code=503, detail="LLM API key is not configured (set LLM_API_KEY in .env)")

    prompt = build_application_prompt(
        offer={
            "title": offer.title,
            "company": offer.company,
            "location": offer.location,
            "technologies": offer.technologies,
            "salary_min": offer.salary_min,
            "salary_max": offer.salary_max,
            "salary_period": offer.salary_period,
            "description": offer.description,
        },
        cv_text=cv_text,
        instructions=request.instructions,
    )

    try:
        result = service.generate(
            prompt,
            system_prompt=request.system_prompt.strip() or None,
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")

    if not result.content:
        raise HTTPException(status_code=502, detail="Model returned an empty message")

    stored = GeneratedMessage(
        offer_id=offer.id,
        cv_id=request.cv_id,
        model=result.model,
        message=result.content,
        instructions=request.instructions or None,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
    db.add(stored)
    db.commit()
    db.refresh(stored)

    return GenerateResponse(
        id=stored.id,
        message=result.content,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


@router.get("/ai/messages/{offer_id}", response_model=list[MessageInfo])
async def list_messages(offer_id: int, db: Session = Depends(get_db)):
    """Message generation history for an offer (newest first)."""
    rows = (
        db.query(GeneratedMessage)
        .filter(GeneratedMessage.offer_id == offer_id)
        .order_by(GeneratedMessage.created_at.desc())
        .all()
    )
    return [
        MessageInfo(
            id=m.id,
            offer_id=m.offer_id,
            model=m.model,
            message=m.message,
            instructions=m.instructions,
            prompt_tokens=m.prompt_tokens,
            completion_tokens=m.completion_tokens,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in rows
    ]


@router.delete("/ai/messages/{message_id}")
async def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Delete a stored generated message."""
    m = db.query(GeneratedMessage).filter(GeneratedMessage.id == message_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(m)
    db.commit()
    return {"deleted_id": message_id}
