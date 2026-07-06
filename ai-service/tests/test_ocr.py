"""Tests for OCR helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.ingestion.extract_ocr import maybe_ocr_page, page_has_images


def test_page_has_images_true():
    page = MagicMock()
    page.get_images.return_value = [(1, 2, 3)]
    assert page_has_images(page) is True


def test_maybe_ocr_skips_when_enough_text():
    page = MagicMock()
    text, applied = maybe_ocr_page(
        page,
        "x" * 100,
        min_chars=40,
        lang="eng",
        enabled=True,
    )
    assert applied is False
    assert text.startswith("x")


@patch("app.ingestion.extract_ocr.ocr_page_text", return_value="OCR extracted formula table with enough characters for ingest")
def test_maybe_ocr_applies_when_sparse_text(mock_ocr):
    page = MagicMock()
    page.get_images.return_value = [(1,)]
    text, applied = maybe_ocr_page(
        page,
        "short",
        min_chars=40,
        lang="eng",
        enabled=True,
    )
    assert applied is True
    assert "OCR extracted" in text
    mock_ocr.assert_called_once()
