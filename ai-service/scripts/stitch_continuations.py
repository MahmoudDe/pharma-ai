"""Merge "(continued)" formulation records into their parents.

Multi-page tables (e.g. "Prescription 5.10 Damage care shampoo" on page 144,
"Prescription 5.10 (continued)" on page 145) are ingested as two records,
leaving the parent with an incomplete ingredient list that fails the KBS
percentage-sum check. This stitches each continuation into its parent and
removes the continuation record and its KBS report.

Usage:
    python -m scripts.stitch_continuations [--dry-run] [--validate]
"""
from __future__ import annotations

import argparse
import logging
import re
import sys

from app.formulation.store import get_store
from app.formulation.store_base import FormulationSearchFilters
from app.ingestion.segments import build_vector_text
from app.kbs import report_store


logger = logging.getLogger(__name__)

_CONTINUED = re.compile(r"^(?P<prefix>.+?)\s*\(continued\)\s*$", re.I)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s :: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate", action="store_true", help="Run KBS batch validation after.")
    args = parser.parse_args(argv)

    store = get_store()
    records = store.search(FormulationSearchFilters(limit=100000))
    by_id = {r.id: r for r in records}

    stitched = 0
    for record in records:
        match = _CONTINUED.match(record.name.strip())
        if not match:
            continue
        prefix = match.group("prefix").strip()
        # parent: same doc, name starts with the prefix, an earlier page,
        # and not itself a continuation
        candidates = [
            r
            for r in by_id.values()
            if r.doc_id == record.doc_id
            and r.id != record.id
            and r.name.strip().lower().startswith(prefix.lower())
            and not _CONTINUED.match(r.name.strip())
            and r.pdf_page <= record.pdf_page
        ]
        if not candidates:
            logger.warning("No parent found for %r (doc=%s)", record.name, record.doc_id)
            continue
        parent = max(candidates, key=lambda r: r.pdf_page)

        existing = {
            (i.normalized_name or i.raw_name).strip().lower() for i in parent.ingredients
        }
        added = 0
        for ing in record.ingredients:
            key = (ing.normalized_name or ing.raw_name).strip().lower()
            if key and key in existing:
                continue
            parent.ingredients.append(ing)
            existing.add(key)
            added += 1

        logger.info(
            "%s%r (p.%d) += %r (p.%d): %d ingredients added",
            "[dry-run] " if args.dry_run else "",
            parent.name[:50],
            parent.pdf_page,
            record.name[:40],
            record.pdf_page,
            added,
        )
        stitched += 1
        if args.dry_run:
            continue

        parent.source_text = f"{parent.source_text}\n\n{record.source_text}".strip()
        if record.procedure and not parent.procedure:
            parent.procedure = record.procedure
        parent.vector_text = build_vector_text(
            parent.name, parent.product_types, parent.ingredients, parent.procedure
        )
        store.upsert(parent)
        store.delete(record.id)
        report_store.delete_report(record.id)
        del by_id[record.id]

    logger.info("%s%d continuation(s) stitched", "[dry-run] " if args.dry_run else "", stitched)

    if args.validate and not args.dry_run:
        from app.kbs.service import validate_all

        summary = validate_all()
        logger.info("KBS re-validation: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
