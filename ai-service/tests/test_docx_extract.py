from pathlib import Path

from app.ingestion.extract_docx import extract_docx


def test_extract_docx_reads_project_sample():
    docs = Path(__file__).resolve().parent.parent.parent / "docs"
    candidates = list(docs.glob("*.docx"))
    if not candidates:
        return
    pages = list(extract_docx(candidates[0]))
    assert len(pages) >= 1
    assert len(pages[0].text) >= 40
