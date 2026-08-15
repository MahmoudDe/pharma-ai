#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.ingestion.chunk import Chunk
from app.ingestion.index import get_client
from app.retrieval.bm25_index import Bm25Index, clear_bm25_index


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    client = get_client()
    name = settings.qdrant_collection

    clear_bm25_index()
    index = Bm25Index()
    offset = None
    total = 0

    while True:
        points, offset = client.scroll(
            collection_name=name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        chunks: list[Chunk] = []
        for point in points:
            payload = point.payload or {}
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    doc_id=str(payload.get("doc_id", "")),
                    doc_title=str(payload.get("doc_title", "")),
                    pdf_page=int(payload.get("pdf_page") or payload.get("page") or 0),
                    printed_page=payload.get("printed_page"),
                    chunk_index=int(payload.get("chunk_index") or 0),
                    text=text,
                    is_formula=bool(payload.get("is_formula")),
                    chunk_type=str(payload.get("chunk_type", "prose")),
                    section_title=payload.get("section_title"),
                    product_types=list(payload.get("product_types") or []),
                    text_hash=str(payload.get("text_hash", "")),
                    formulation_id=payload.get("formulation_id"),
                    formula_name=payload.get("formula_name"),
                    ingredient_count=int(payload.get("ingredient_count") or 0),
                    extraction_confidence=float(payload.get("extraction_confidence") or 0.0),
                    extraction_method=str(payload.get("extraction_method") or ""),
                )
            )
        index.add_chunks(chunks)
        total += len(chunks)
        if offset is None:
            break

    index.save()
    logger.info("BM25 index rebuilt with %d chunk(s)", len(index.records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
