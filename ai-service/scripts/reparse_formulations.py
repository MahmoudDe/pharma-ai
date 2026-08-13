"""Re-parse stored formulations from their source_text after parser fixes.

Surgical alternative to `run_ingest --force`: updates ingredients, vector_text
and extraction metadata in the formulation store from the already-stored
source blocks, without touching Qdrant or the BM25 index. Run KBS
re-validation afterwards (or pass --validate).

Usage:
    python -m scripts.reparse_formulations [--dry-run] [--validate]
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.formulation.parsers import parse_formula_block
from app.formulation.store import get_store
from app.formulation.store_base import FormulationSearchFilters
from app.ingestion.segments import build_vector_text


logger = logging.getLogger(__name__)


def _sum_deviation(ingredients) -> float | None:
    """Distance of the percent sum from 100; None when too few amounts.

    With a q.s. line present ("water to 100"), only overshoot counts —
    the fill line legitimately absorbs any remainder below 100.
    """
    from app.kbs.facts import is_qs_line

    amounts = [i.amount for i in ingredients if i.amount]
    if len(amounts) < 2:
        return None
    total = sum(amounts)
    if any(is_qs_line(i) or (i.unit or "").strip().lower() == "qs" for i in ingredients):
        return max(0.0, total - 100.0)
    return abs(total - 100.0)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s :: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    parser.add_argument("--validate", action="store_true", help="Run KBS batch validation after.")
    args = parser.parse_args(argv)

    store = get_store()
    records = store.search(FormulationSearchFilters(limit=100000))
    logger.info("Re-parsing %d formulations from stored source_text", len(records))

    changed = 0
    improved_amounts = 0
    for record in records:
        if not record.source_text.strip():
            continue
        ingredients, method, confidence = parse_formula_block(record.source_text)
        if len(ingredients) < 2:
            continue  # keep the existing parse rather than degrade

        old_with_amounts = sum(1 for i in record.ingredients if i.amount)
        new_with_amounts = sum(1 for i in ingredients if i.amount)
        old_names = [(i.raw_name, i.amount, i.unit) for i in record.ingredients]
        new_names = [(i.raw_name, i.amount, i.unit) for i in ingredients]
        if new_names == old_names:
            continue
        if record.extraction_method == "llm" and new_with_amounts < old_with_amounts:
            continue  # never degrade an LLM-enriched record with a weaker regex parse
        if new_with_amounts < old_with_amounts:
            # fewer dosed lines is acceptable only when the new parse is
            # clearly more plausible (percent sum closer to 100) — e.g. the
            # old parse mistook row numbers or "99%" grades for amounts
            old_dev = _sum_deviation(record.ingredients)
            new_dev = _sum_deviation(ingredients)
            if new_dev is None or (old_dev is not None and new_dev >= old_dev):
                continue

        changed += 1
        if new_with_amounts > old_with_amounts:
            improved_amounts += 1
        if args.dry_run:
            continue

        record.ingredients = ingredients
        record.extraction_method = method
        record.confidence = confidence
        record.vector_text = build_vector_text(
            record.name, record.product_types, ingredients, record.procedure
        )
        store.upsert(record)

    logger.info(
        "%s%d formulations updated (%d with more parsed amounts than before)",
        "[dry-run] " if args.dry_run else "",
        changed,
        improved_amounts,
    )

    if args.validate and not args.dry_run:
        from app.kbs.service import validate_all

        summary = validate_all()
        logger.info("KBS re-validation: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
