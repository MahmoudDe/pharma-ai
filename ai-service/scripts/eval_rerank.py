#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.retrieval_eval import GOLDEN_QUESTIONS, load_golden_expectations, evaluate_retrieval


@dataclass
class ModeReport:
    name: str
    passed: int = 0
    failed: int = 0
    avg_top_score: float = 0.0
    ndcg: float = 0.0
    errors: list[str] = field(default_factory=list)


@contextmanager
def _rerank_mode(*, cross_encoder: bool, bm25: bool):
    import os

    from app.config import get_settings

    keys = {
        "ENABLE_CROSS_ENCODER_RERANK": str(cross_encoder).lower(),
        "ENABLE_BM25_HYBRID": str(bm25).lower(),
    }
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _ndcg_at_k(relevant_ranks: list[int], k: int) -> float:
    """Binary relevance NDCG@k from 1-based ranks of relevant items."""
    if not relevant_ranks:
        return 0.0
    dcg = sum(1.0 / math.log2(r + 1) for r in relevant_ranks if r <= k)
    ideal_hits = min(len(relevant_ranks), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def _run_mode(name: str, *, cross_encoder: bool, bm25: bool, top_k: int) -> ModeReport:
    golden = load_golden_expectations()
    report = ModeReport(name=name)
    ndcg_scores: list[float] = []

    with _rerank_mode(cross_encoder=cross_encoder, bm25=bm25):
        for question in GOLDEN_QUESTIONS:
            result = evaluate_retrieval(
                question,
                top_k=top_k,
                golden=golden.get(question),
            )
            if result.errors:
                report.failed += 1
                report.errors.extend(f"{question}: {e}" for e in result.errors)
            else:
                report.passed += 1
            if result.chunks:
                report.avg_top_score += result.chunks[0].score

            g = golden.get(question)
            if g and g.min_formula_in_top_k:
                relevant_ranks = [
                    i + 1
                    for i, c in enumerate(result.chunks[: g.top_k])
                    if c.ingredient_count >= (g.min_ingredient_count or 2)
                ]
                ndcg_scores.append(_ndcg_at_k(relevant_ranks, g.top_k))

    n = len(GOLDEN_QUESTIONS) or 1
    report.avg_top_score /= n
    if ndcg_scores:
        report.ndcg = sum(ndcg_scores) / len(ndcg_scores)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare rerank modes on golden queries.")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    modes = [
        _run_mode("heuristic_only", cross_encoder=False, bm25=False, top_k=args.top_k),
        _run_mode("bm25+heuristic", cross_encoder=False, bm25=True, top_k=args.top_k),
        _run_mode("bm25+cross_encoder", cross_encoder=True, bm25=True, top_k=args.top_k),
    ]

    print(f"{'Mode':<22} {'Pass':>6} {'Fail':>6} {'NDCG@k':>8} {'AvgTop1':>8}")
    print("-" * 54)
    for m in modes:
        ndcg = m.ndcg
        print(
            f"{m.name:<22} {m.passed:>6} {m.failed:>6} {ndcg:>8.3f} {m.avg_top_score:>8.3f}"
        )
        for err in m.errors[:3]:
            print(f"  ! {err}")
        if len(m.errors) > 3:
            print(f"  ... +{len(m.errors) - 3} more")

    best = max(modes, key=lambda x: (x.passed, x.ndcg))
    print(f"\nBest mode: {best.name} ({best.passed}/{best.passed + best.failed} pass)")
    return 0 if modes[-1].failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
