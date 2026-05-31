"""Corpus / index statistics for admin UI."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter

from app.formulation.store import DB_PATH
from app.ingestion.index import collection_stats
from app.services.health_check import readiness_report
from app.retrieval.bm25_index import get_bm25_index
from app.sources.pdf_map import list_source_documents


router = APIRouter(prefix="/corpus", tags=["corpus"])


@router.get("/stats")
def corpus_stats() -> dict:
    report = readiness_report()
    stats = collection_stats()
    formulations = 0
    ingredients = 0
    if DB_PATH.is_file():
        conn = sqlite3.connect(DB_PATH)
        formulations = int(conn.execute("SELECT COUNT(*) FROM formulations").fetchone()[0])
        ingredients = int(conn.execute("SELECT COUNT(DISTINCT normalized_name) FROM ingredients").fetchone()[0])
        conn.close()
    return {
        "ready": report.ok,
        "dependencies": [
            {"name": d.name, "ok": d.ok, "detail": d.detail} for d in report.dependencies
        ],
        "qdrant_points": int(stats.get("points_count") or 0),
        "bm25_documents": len(get_bm25_index().records),
        "formulation_count": formulations,
        "ingredient_count": ingredients,
        "source_documents": list_source_documents(),
    }
