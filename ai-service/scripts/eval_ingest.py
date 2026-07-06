#!/usr/bin/env python3
"""Audit structured formula completeness on the ingested corpus (free, no LLM)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.ingest_quality import IngestQualityThresholds, audit_ingest_quality

_DEFAULT_THRESHOLDS = IngestQualityThresholds()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure ingestion/parser quality on formulations.db."
    )
    parser.add_argument(
        "--min-6plus",
        type=float,
        default=_DEFAULT_THRESHOLDS.min_share_6plus_ingredients,
        help="Minimum share of formulas with >=6 ingredients (default 0.45)",
    )
    parser.add_argument(
        "--min-amounts",
        type=float,
        default=_DEFAULT_THRESHOLDS.min_share_with_amounts,
        help="Minimum share with numeric amounts",
    )
    parser.add_argument(
        "--min-procedure",
        type=float,
        default=_DEFAULT_THRESHOLDS.min_share_with_procedure,
        help="Minimum share with procedure steps",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print metrics without failing on thresholds",
    )
    args = parser.parse_args()

    thresholds = IngestQualityThresholds(
        min_share_6plus_ingredients=args.min_6plus,
        min_share_with_amounts=args.min_amounts,
        min_share_with_procedure=args.min_procedure,
    )
    report = audit_ingest_quality(thresholds=thresholds)

    print(f"Formulas in store: {report.total_formulas}")
    print(f"  >=6 ingredients:  {report.share_6plus_ingredients:.1%}")
    print(f"  with amounts:     {report.share_with_amounts:.1%}")
    print(f"  with procedure:   {report.share_with_procedure:.1%}")
    print(f"  high confidence:  {report.share_high_confidence:.1%}")
    print(f"  2-ingredient only:{report.share_2_ingredient_only:.1%}")
    print(f"  median / avg ing: {report.median_ingredients:.1f} / {report.avg_ingredients:.1f}")
    if report.by_method:
        methods = ", ".join(f"{k}={v}" for k, v in sorted(report.by_method.items()))
        print(f"  by method:        {methods}")

    if report.thin_examples:
        print("\nThin examples (high confidence, <6 ingredients):")
        for line in report.thin_examples:
            print(f"  - {line}")

    if report.failures:
        print("\nThreshold failures:")
        for err in report.failures:
            print(f"  FAIL: {err}")
        return 0 if args.report_only else 1

    print("\nIngest quality thresholds met.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
