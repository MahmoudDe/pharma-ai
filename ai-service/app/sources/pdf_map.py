"""Map doc_id slugs to PDF files under docs/."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.ingestion.extract import doc_id_from_path


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


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
    """Resolve a PDF by slug doc_id, with fallbacks for legacy title-based citations."""
    key = doc_id.strip()
    if not key:
        return None
    index = pdf_index()
    if key in index:
        return index[key]
    lower = key.lower()
    if lower in index:
        return index[lower]

    slug = _slugify(key)
    if slug and slug in index:
        return index[slug]

    # Prefix / containment match for truncated titles or old UI labels.
    if slug:
        for did, path in index.items():
            if did.startswith(slug) or slug.startswith(did):
                return path
            if path.stem == key or path.stem.lower() == lower:
                return path
    return None


def list_source_documents() -> list[dict[str, str]]:
    return [
        {"doc_id": doc_id, "filename": path.name}
        for doc_id, path in sorted(pdf_index().items(), key=lambda x: x[1].name)
    ]
