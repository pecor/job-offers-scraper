"""CV document endpoints: upload (PDF/TXT with OCR fallback), list, get, delete."""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CVDocument
from app.services.cv_extractor import extract_text, CvExtractionError

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
TEXT_PREVIEW_LENGTH = 300


class CVDocumentInfo(BaseModel):
    id: int
    filename: str
    extraction_method: str | None
    text_length: int
    created_at: str | None

    class Config:
        from_attributes = True


class CVUploadResponse(CVDocumentInfo):
    preview: str


class CVUpdateRequest(BaseModel):
    text_content: str = Field(min_length=1)


def _to_info(doc: CVDocument) -> CVDocumentInfo:
    return CVDocumentInfo(
        id=doc.id,
        filename=doc.filename,
        extraction_method=doc.extraction_method,
        text_length=len(doc.text_content or ""),
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.get("/cv", response_model=list[CVDocumentInfo])
async def list_cvs(db: Session = Depends(get_db)):
    """List saved CV documents (without full text)."""
    docs = db.query(CVDocument).order_by(CVDocument.created_at.desc()).all()
    return [_to_info(d) for d in docs]


@router.get("/cv/{cv_id}")
async def get_cv(cv_id: int, db: Session = Depends(get_db)):
    """Get single CV document with full text."""
    doc = db.query(CVDocument).filter(CVDocument.id == cv_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV document not found")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "extraction_method": doc.extraction_method,
        "text_content": doc.text_content,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/cv/upload", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload CV (PDF or TXT). PDFs without a text layer go through OCR (pol+eng)."""
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        text, method = extract_text(file.filename or "", data)
    except CvExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not text:
        raise HTTPException(status_code=422, detail="No text could be extracted from the file")

    doc = CVDocument(
        filename=file.filename or "cv",
        content_type=file.content_type,
        extraction_method=method,
        text_content=text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(f"CV uploaded: {doc.filename} (method={method}, {len(text)} chars)")
    info = _to_info(doc)
    return CVUploadResponse(**info.model_dump(), preview=text[:TEXT_PREVIEW_LENGTH])


@router.put("/cv/{cv_id}", response_model=CVDocumentInfo)
async def update_cv(cv_id: int, request: CVUpdateRequest, db: Session = Depends(get_db)):
    """Edit extracted CV text (e.g. fix OCR errors)."""
    doc = db.query(CVDocument).filter(CVDocument.id == cv_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV document not found")

    doc.text_content = request.text_content.strip()
    if not doc.text_content:
        raise HTTPException(status_code=422, detail="CV text cannot be empty")
    db.commit()
    db.refresh(doc)
    logger.info(f"CV updated: {doc.filename} ({len(doc.text_content)} chars)")
    return _to_info(doc)


@router.delete("/cv/{cv_id}")
async def delete_cv(cv_id: int, db: Session = Depends(get_db)):
    """Delete CV document."""
    doc = db.query(CVDocument).filter(CVDocument.id == cv_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV document not found")
    db.delete(doc)
    db.commit()
    return {"deleted_id": cv_id}
