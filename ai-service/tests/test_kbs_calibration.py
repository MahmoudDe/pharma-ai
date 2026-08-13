"""Regression guard: the KBS 'verified' badge measured against the golden set.

The golden set (scripts/golden_kbs.json) holds labeled record snapshots that
were independently screened and manually adjudicated. If a rule or weight
change degrades the badge below these floors, this test fails — measured
values at calibration time were precision 0.957 / recall 1.0 (see
scripts/eval_kbs.py for a detailed breakdown).
"""
from __future__ import annotations

from scripts.eval_kbs import evaluate


def test_verified_badge_precision_and_recall():
    metrics = evaluate()
    assert metrics["n"] >= 40, "golden set unexpectedly small"
    assert metrics["precision"] >= 0.90, (
        f"verified-badge precision regressed: {metrics['precision']} — {metrics['misses']}"
    )
    assert metrics["recall"] >= 0.90, (
        f"verified-badge recall regressed: {metrics['recall']} — {metrics['misses']}"
    )
