from __future__ import annotations

from app.eval.corpus_health import summarize_ocr_from_manifest


def test_summarize_ocr_empty_manifest():
    summary = summarize_ocr_from_manifest()
    assert summary.documents_with_ocr >= 0
    assert summary.total_ocr_pages >= 0
