"""CV text extraction: PDF text layer first, OCR fallback for scanned documents."""

import logging
import io
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum characters of text layer below which we treat the PDF as scanned
MIN_TEXT_LAYER_LENGTH = 100

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


class CvExtractionError(Exception):
    pass


def _extract_pdf_text_layer(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as e:
        raise CvExtractionError(f"Failed to read PDF: {e}") from e


def _extract_pdf_ocr(data: bytes) -> str:
    import pytesseract
    from pdf2image import convert_from_bytes

    try:
        images = convert_from_bytes(data, dpi=200)
        parts = []
        for i, image in enumerate(images, start=1):
            logger.info(f"OCR: processing page {i}/{len(images)}")
            text = pytesseract.image_to_string(image, lang="pol+eng")
            parts.append(text.strip())
        return "\n".join(parts).strip()
    except Exception as e:
        raise CvExtractionError(f"OCR failed: {e}") from e


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    """
    Extract text from an uploaded CV file.

    Returns:
        Tuple (text, method) where method is one of: pdf-text, ocr, plain.

    Raises:
        CvExtractionError: when the file cannot be processed.
    """
    from pathlib import Path

    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise CvExtractionError(
            f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if extension == ".txt":
        try:
            return data.decode("utf-8").strip(), "plain"
        except UnicodeDecodeError:
            try:
                return data.decode("utf-8-sig").strip(), "plain"
            except UnicodeDecodeError as e:
                raise CvExtractionError(f"Cannot decode text file: {e}") from e

    # PDF: text layer first, OCR when the document looks scanned
    text_layer = _extract_pdf_text_layer(data)
    if len(text_layer) >= MIN_TEXT_LAYER_LENGTH:
        logger.info(f"CV: extracted {len(text_layer)} chars from PDF text layer")
        return text_layer, "pdf-text"

    logger.info("CV: text layer empty or tiny, falling back to OCR")
    ocr_text = _extract_pdf_ocr(data)
    if not ocr_text:
        raise CvExtractionError("OCR extracted no text from the document")
    return ocr_text, "ocr"
