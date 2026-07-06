"""Corpus-level ingestion quality metrics for structured formulations."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.formulation.store import list_formulations


@dataclass(slots=True)
class IngestQualityThresholds:
    """Minimum acceptable shares (0–1) for product-ready corpus quality."""

    min_share_6plus_ingredients: float = 0.45
    min_share_with_amounts: float = 0.80
    min_share_with_procedure: float = 0.25
    min_median_ingredients: float = 5.0
    max_share_2_ingredient_only: float = 0.08


@dataclass(slots=True)
class IngestQualityReport:
    total_formulas: int
    share_6plus_ingredients: float
    share_with_amounts: float
    share_with_procedure: float
    share_high_confidence: float
    share_2_ingredient_only: float
    median_ingredients: float
    avg_ingredients: float
    by_method: dict[str, int] = field(default_factory=dict)
    thin_examples: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def audit_ingest_quality(
  *,
  thresholds: IngestQualityThresholds | None = None,
  thin_example_limit: int = 8,
) -> IngestQualityReport:
    """Measure how complete extracted formulas are on the ingested corpus."""
    thresholds = thresholds or IngestQualityThresholds()
    records = list_formulations(limit=100_000)
    total = len(records)

    if total == 0:
        return IngestQualityReport(
            total_formulas=0,
            share_6plus_ingredients=0.0,
            share_with_amounts=0.0,
            share_with_procedure=0.0,
            share_high_confidence=0.0,
            share_2_ingredient_only=0.0,
            median_ingredients=0.0,
            avg_ingredients=0.0,
            failures=["no formulations in store — run ingestion first"],
        )

    ing_counts = [len(r.ingredients) for r in records]
    six_plus = sum(1 for c in ing_counts if c >= 6)
    with_amounts = sum(
        1 for r in records if any(i.amount is not None for i in r.ingredients)
    )
    with_procedure = sum(1 for r in records if r.procedure)
    high_conf = sum(1 for r in records if r.confidence >= 0.85)
    two_only = sum(1 for c in ing_counts if c == 2)

    by_method: dict[str, int] = {}
    for rec in records:
        by_method[rec.extraction_method] = by_method.get(rec.extraction_method, 0) + 1

    thin = sorted(
        [r for r in records if len(r.ingredients) < 6],
        key=lambda r: (-r.confidence, len(r.ingredients)),
    )
    thin_examples = [
        f"{r.name[:50]} ({len(r.ingredients)} ing, {r.extraction_method}, conf={r.confidence:.2f})"
        for r in thin[:thin_example_limit]
    ]

    share_6 = six_plus / total
    share_amt = with_amounts / total
    share_proc = with_procedure / total
    share_hi = high_conf / total
    share_two = two_only / total
    med = _median(ing_counts)
    avg = sum(ing_counts) / total

    failures: list[str] = []
    if share_6 < thresholds.min_share_6plus_ingredients:
        failures.append(
            f">=6 ingredients: {share_6:.1%} < {thresholds.min_share_6plus_ingredients:.0%}"
        )
    if share_amt < thresholds.min_share_with_amounts:
        failures.append(
            f"with amounts: {share_amt:.1%} < {thresholds.min_share_with_amounts:.0%}"
        )
    if share_proc < thresholds.min_share_with_procedure:
        failures.append(
            f"with procedure: {share_proc:.1%} < {thresholds.min_share_with_procedure:.0%}"
        )
    if med < thresholds.min_median_ingredients:
        failures.append(
            f"median ingredients: {med:.1f} < {thresholds.min_median_ingredients:.1f}"
        )
    if share_two > thresholds.max_share_2_ingredient_only:
        failures.append(
            f"2-ingredient-only: {share_two:.1%} > {thresholds.max_share_2_ingredient_only:.0%}"
        )

    return IngestQualityReport(
        total_formulas=total,
        share_6plus_ingredients=share_6,
        share_with_amounts=share_amt,
        share_with_procedure=share_proc,
        share_high_confidence=share_hi,
        share_2_ingredient_only=share_two,
        median_ingredients=med,
        avg_ingredients=avg,
        by_method=by_method,
        thin_examples=thin_examples,
        failures=failures,
    )
