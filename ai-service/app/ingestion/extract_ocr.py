"""OCR fallback for scanned PDF pages."""
from __future__ import annotations

import logging

import fitz

from app.ingestion.extract import _normalize


logger = logging.getLogger(__name__)


def page_has_images(page: fitz.Page) -> bool:
    try:
        return bool(page.get_images())
    except Exception:
        return False


def ocr_page_text(page: fitz.Page, *, lang: str = "eng") -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        logger.warning("OCR dependencies missing: %s", exc)
        return ""

    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        raw = pytesseract.image_to_string(img, lang=lang)
        return _normalize(raw)
    except Exception as exc:
        logger.warning("OCR failed on page %s: %s", page.number + 1, exc)
        return ""


def maybe_ocr_page(
    page: fitz.Page,
    extracted_text: str,
    *,
    min_chars: int,
    lang: str,
    enabled: bool,
) -> tuple[str, bool]:
    if not enabled:
        return extracted_text, False
    if len(extracted_text.strip()) >= min_chars:
        return extracted_text, False
    if not page_has_images(page):
        return extracted_text, False

    ocr_text = ocr_page_text(page, lang=lang)
    if len(ocr_text.strip()) < min_chars:
        return extracted_text, False
    return ocr_text, True
