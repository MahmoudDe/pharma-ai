"""Deprecated: use `python -m app.ingestion.run_ingest` for unified PDF -> SQLite + Qdrant."""
from __future__ import annotations

import argparse
import logging
import sys

from app.config import get_settings
from app.ingestion.extract import discover_pdfs
from app.ingestion.run_ingest import ingest_pdf


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    logger.warning(
        "run_extract is deprecated; use: python -m app.ingestion.run_ingest [--force]"
    )

    parser = argparse.ArgumentParser(
        description="(Deprecated) Re-run unified ingest for docs directory.",
    )
    parser.add_argument("--docs", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-llm", action="store_true", help="Ignored; use ingest pipeline.")
    args = parser.parse_args(argv)

    settings = get_settings()
    docs_dir = settings.docs_dir if not args.docs else args.docs
    from pathlib import Path

    pdfs = discover_pdfs(Path(docs_dir))
    total = 0
    for pdf in pdfs:
        n_formulas, _ = ingest_pdf(Path(pdf))
        total += n_formulas
    logger.info("Extracted %d formulations via unified ingest", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
