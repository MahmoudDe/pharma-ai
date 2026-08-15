from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

from app.config import get_settings
from app.formulation.store import clear_all_formulations, init_db, upsert_formulation
from app.ingestion.embed import embed_passages
from app.ingestion.extract import discover_pdfs, doc_id_from_path, extract_pdf
from app.ingestion.extract_docx import discover_docx, extract_docx
from app.ingestion.extract_xlsx import discover_xlsx, extract_xlsx
from app.retrieval.bm25_index import append_chunks_to_bm25, clear_bm25_index
from app.ingestion.index import (
    collection_stats,
    ensure_collection,
    reset_collection,
    reset_dedup_cache,
    upsert_chunks,
)
from app.ingestion.unified import process_pages


logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ingested.json"


def _file_hash(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk_size):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Manifest at %s is corrupt; ignoring", MANIFEST_PATH)
        return {}


def _save_manifest(manifest: dict[str, dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _batched_chunks(chunks, size: int):
    batch = []
    for chunk in chunks:
        batch.append(chunk)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def ingest_document(
    path: Path,
    *,
    batch_size: int = 64,
    sqlite_only: bool = False,
) -> tuple[int, int, int]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        pages = list(extract_docx(path))
    elif suffix == ".xlsx":
        pages = list(extract_xlsx(path))
    else:
        pages = list(extract_pdf(path))
    ocr_pages = sum(1 for p in pages if getattr(p, "ocr_applied", False))
    settings = get_settings()
    logger.info("[%s] %d pages with text", path.name, len(pages))

    formulations, chunks = process_pages(
        pages,
        prose_size=settings.chunk_char_size,
        prose_overlap=settings.chunk_char_overlap,
    )
    logger.info(
        "[%s] %d formulations, %d chunks",
        path.name,
        len(formulations),
        len(chunks),
    )

    init_db()
    for record in formulations:
        upsert_formulation(record)

    # KBS: score precision of every extracted record; never blocks ingestion.
    try:
        from app.kbs.service import validate_and_rescore

        flagged = 0
        for record in formulations:
            report = validate_and_rescore(record)
            if report.status == "low_precision":
                flagged += 1
        if formulations:
            logger.info(
                "[%s] KBS validated %d formulations (%d flagged low precision)",
                path.name,
                len(formulations),
                flagged,
            )
    except Exception:
        logger.exception("[%s] KBS validation failed; records stored without reports", path.name)

    if not sqlite_only and chunks:
        for batch in tqdm(
            list(_batched_chunks(chunks, batch_size)),
            desc=f"{path.name} embed",
            unit="batch",
        ):
            vectors = embed_passages([c.text for c in batch], batch_size=batch_size)
            upsert_chunks(batch, vectors)
        append_chunks_to_bm25(chunks)

    return len(formulations), len(chunks), ocr_pages


def ingest_pdf(
    path: Path,
    *,
    batch_size: int = 64,
    sqlite_only: bool = False,
) -> tuple[int, int, int]:
    return ingest_document(path, batch_size=batch_size, sqlite_only=sqlite_only)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Unified ingest: PDFs/DOCX/XLSX -> formulations + Qdrant chunks.",
    )
    parser.add_argument("--docs", default=None, help="Path to docs directory.")
    parser.add_argument(
        "--pdf-only",
        action="store_true",
        help="Skip DOCX files (PDF only).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even if PDF hash unchanged.",
    )
    parser.add_argument(
        "--sqlite-only",
        action="store_true",
        help="Update formulations.db only (skip Qdrant embed/upsert).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    docs_dir = Path(args.docs) if args.docs else Path(settings.docs_dir)
    if not docs_dir.exists():
        logger.error("Docs directory not found: %s", docs_dir)
        return 1

    if args.force:
        clear_all_formulations()
        clear_bm25_index()
    if not args.sqlite_only:
        if args.force:
            reset_collection()
        ensure_collection()
        reset_dedup_cache()
    manifest = _load_manifest()

    pdfs = discover_pdfs(docs_dir)
    docx_files = [] if args.pdf_only else discover_docx(docs_dir)
    xlsx_files = [] if args.pdf_only else discover_xlsx(docs_dir)
    sources: list[tuple[Path, str]] = (
        [(p, "pdf") for p in pdfs]
        + [(p, "docx") for p in docx_files]
        + [(p, "xlsx") for p in xlsx_files]
    )
    if not sources:
        logger.warning("No PDF/DOCX/XLSX files found in %s", docs_dir)
        return 0

    total_chunks = 0
    total_formulas = 0
    seen_content_hashes: dict[str, str] = {}
    for source_path, kind in sources:
        doc_id = doc_id_from_path(source_path)
        digest = _file_hash(source_path)
        if digest in seen_content_hashes:
            logger.info(
                "[%s] duplicate content of %s (SHA-256), skipping",
                source_path.name,
                seen_content_hashes[digest],
            )
            continue
        seen_content_hashes[digest] = source_path.name
        if not args.force and manifest.get(doc_id, {}).get("sha256") == digest:
            logger.info("[%s] unchanged, skipping (use --force)", source_path.name)
            continue

        n_formulas, n_chunks, ocr_pages = ingest_document(
            source_path, sqlite_only=args.sqlite_only
        )
        if n_formulas:
            import sqlite3
            from app.formulation.store import DB_PATH

            conn = sqlite3.connect(DB_PATH)
            avg_ing = conn.execute(
                """
                SELECT AVG(cnt) FROM (
                    SELECT COUNT(*) cnt FROM ingredients
                    WHERE formulation_id IN (
                        SELECT id FROM formulations WHERE doc_id = ?
                    )
                    GROUP BY formulation_id
                )
                """,
                (doc_id,),
            ).fetchone()[0]
            conn.close()
            logger.info(
                "[%s] avg ingredients per formula: %.1f",
                source_path.name,
                avg_ing or 0,
            )
        manifest[doc_id] = {
            "doc_id": doc_id,
            "filename": source_path.name,
            "kind": kind,
            "sha256": digest,
            "formulations": n_formulas,
            "chunks": n_chunks,
            "ocr_pages_count": ocr_pages,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_manifest(manifest)
        total_formulas += n_formulas
        total_chunks += n_chunks

    if args.sqlite_only:
        logger.info(
            "SQLite-only ingest complete. Formulations: %d, chunks prepared: %d.",
            total_formulas,
            total_chunks,
        )
    else:
        stats = collection_stats()
        logger.info(
            "Ingestion complete. Formulations: %d, chunks this run: %d. Qdrant points: %d.",
            total_formulas,
            total_chunks,
            stats["points_count"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
