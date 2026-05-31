"""Map doc_id slugs to PDF files under docs/."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.ingestion.extract import doc_id_from_path


@lru_cache(maxsize=1)
def pdf_index() -> dict[str, Path]:
    settings = get_settings()
    docs = Path(settings.docs_dir)
    if not docs.is_dir():
        return {}
    out: dict[str, Path] = {}
    for path in sorted(docs.glob("*.pdf")):
        out[doc_id_from_path(path)] = path
    return out


def resolve_pdf_path(doc_id: str) -> Path | None:
    return pdf_index().get(doc_id.strip().lower()) or pdf_index().get(doc_id.strip())


def list_source_documents() -> list[dict[str, str]]:
    return [
        {"doc_id": doc_id, "filename": path.name}
        for doc_id, path in sorted(pdf_index().items(), key=lambda x: x[1].name)
    ]
