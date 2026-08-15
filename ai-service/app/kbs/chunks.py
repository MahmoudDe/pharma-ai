from __future__ import annotations

import logging


logger = logging.getLogger(__name__)

_qdrant_available: bool | None = None


def reset_availability() -> None:
    global _qdrant_available
    _qdrant_available = None


def fetch_indexed_chunk_texts(formulation_id: str) -> list[str] | None:
    """Chunk texts indexed for this formulation; None = vector store unavailable."""
    global _qdrant_available
    if _qdrant_available is False:
        return None
    try:
        from app.ingestion.index import fetch_chunks_by_formulation_ids

        payloads = fetch_chunks_by_formulation_ids([formulation_id])
        _qdrant_available = True
        return [p.get("text", "") for p in payloads if p.get("text")]
    except Exception:
        if _qdrant_available is None:
            logger.warning(
                "Qdrant unavailable — KBS chunk-level fidelity disabled for this run"
            )
        _qdrant_available = False
        return None
