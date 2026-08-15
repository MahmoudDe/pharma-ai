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
