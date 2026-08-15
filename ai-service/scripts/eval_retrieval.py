#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.retrieval_eval import load_golden_questions, run_retrieval_eval


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval without calling the LLM.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of chunks to retrieve per question")
    parser.add_argument(
        "--score-floor",
        type=float,
        default=0.35,
        help="Minimum acceptable top-1 similarity score",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="Path to golden_retrieval.json (default: scripts/golden_retrieval.json)",
    )
    args = parser.parse_args()

    qs = load_golden_questions(args.golden)
    print(f"Retrieval golden set: {len(qs)} question(s)")
    results = run_retrieval_eval(
        qs,
        top_k=args.top_k,
        score_floor=args.score_floor,
        golden_path=args.golden,
        verbose=True,
    )

    failed = sum(1 for r in results if r.errors)
    passed = len(results) - failed
    print(f"\n{passed}/{len(results)} retrieval checks passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
