"""Corpus / index statistics and ingest operations for the corpus dashboard."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.eval.corpus_health import build_corpus_health_report
from app.formulation.store import DB_PATH, count_formulations, get_store
from app.ingestion.index import collection_stats
from app.ingestion.jobs import enqueue_and_start, get_job, list_jobs, load_manifest
from app.services.health_check import readiness_report
from app.retrieval.bm25_index import get_bm25_index
from app.sources.pdf_map import list_source_documents


router = APIRouter(prefix="/corpus", tags=["corpus"])


class IngestJobRequest(BaseModel):
    force: bool = False
    sqlite_only: bool = False
    pdf_only: bool = False
    docs_dir: str | None = None


@router.get("/stats")
def corpus_stats() -> dict:
    report = readiness_report()
    stats = collection_stats()
    formulations = count_formulations()
    ingredients = 0
    if get_store().backend_name() == "sqlite" and DB_PATH.is_file():
        conn = sqlite3.connect(DB_PATH)
        ingredients = int(
            conn.execute(
                "SELECT COUNT(DISTINCT normalized_name) FROM ingredients"
            ).fetchone()[0]
        )
        conn.close()
    manifest = load_manifest()
    ocr_pages_total = sum(int(m.get("ocr_pages_count") or 0) for m in manifest.values())
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
        "ingest_manifest": manifest,
        "formulation_store": get_store().backend_name(),
        "ocr_pages_total": ocr_pages_total,
        "ocr_documents_count": sum(
            1 for m in manifest.values() if int(m.get("ocr_pages_count") or 0) > 0
        ),
    }


@router.get("/ingest-quality")
def ingest_quality() -> dict:
    health = build_corpus_health_report()
    iq = health.ingest_quality
    return {
        "passed": iq.passed,
        "ocr_enabled": health.ocr_enabled,
        "ocr": {
            "documents_with_ocr": health.ocr.documents_with_ocr,
            "total_ocr_pages": health.ocr.total_ocr_pages,
            "documents": health.ocr.documents,
        },
        "ingest_quality": {
            "total_formulas": iq.total_formulas,
            "share_6plus_ingredients": iq.share_6plus_ingredients,
            "share_with_amounts": iq.share_with_amounts,
            "share_with_procedure": iq.share_with_procedure,
            "share_high_confidence": iq.share_high_confidence,
            "share_2_ingredient_only": iq.share_2_ingredient_only,
            "median_ingredients": iq.median_ingredients,
            "avg_ingredients": iq.avg_ingredients,
            "by_method": iq.by_method,
            "thin_examples": iq.thin_examples,
            "failures": iq.failures,
        },
    }


@router.get("/manifest")
def corpus_manifest() -> dict:
    return {"documents": load_manifest()}


@router.post("/ingest")
def start_ingest(body: IngestJobRequest) -> dict:
    job = enqueue_and_start(
        force=body.force,
        sqlite_only=body.sqlite_only,
        pdf_only=body.pdf_only,
        docs_dir=body.docs_dir,
    )
    return {"job": job.to_dict()}


@router.get("/ingest")
def list_ingest_jobs(limit: int = 20) -> dict:
    jobs = list_jobs(limit=limit)
    return {"jobs": [j.to_dict() for j in jobs], "count": len(jobs)}


@router.get("/ingest/{job_id}")
def get_ingest_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job.to_dict()}
