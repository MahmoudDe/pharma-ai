from __future__ import annotations

from dataclasses import dataclass, field

from app.eval.ingest_quality import IngestQualityReport, audit_ingest_quality
from app.ingestion.run_ingest import _load_manifest


@dataclass(slots=True)
class OcrCorpusSummary:
    documents_with_ocr: int = 0
    total_ocr_pages: int = 0
    documents: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class CorpusHealthReport:
    ingest_quality: IngestQualityReport
    ocr: OcrCorpusSummary
    ocr_enabled: bool


def summarize_ocr_from_manifest() -> OcrCorpusSummary:
    manifest = _load_manifest()
    docs_with_ocr: list[dict] = []
    total_pages = 0
    for entry in manifest.values():
        count = int(entry.get("ocr_pages_count") or 0)
        if count > 0:
            total_pages += count
            docs_with_ocr.append(
                {
                    "doc_id": entry.get("doc_id"),
                    "filename": entry.get("filename"),
                    "ocr_pages_count": count,
                    "formulations": entry.get("formulations"),
                    "chunks": entry.get("chunks"),
                }
            )
    return OcrCorpusSummary(
        documents_with_ocr=len(docs_with_ocr),
        total_ocr_pages=total_pages,
        documents=docs_with_ocr,
    )


def build_corpus_health_report() -> CorpusHealthReport:
    from app.config import get_settings

    settings = get_settings()
    return CorpusHealthReport(
        ingest_quality=audit_ingest_quality(),
        ocr=summarize_ocr_from_manifest(),
        ocr_enabled=settings.ocr_enabled,
    )
