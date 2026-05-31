#!/usr/bin/env python3
"""Golden-question eval: retrieval-only by default; LLM checks are opt-in (costs credits)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reasoning.pipeline import run_chat_pipeline
from app.reasoning.validate import extract_percentages, quote_in_chunk
from app.retrieval.search import search
from app.schemas import ChatTurnRequest
from scripts.retrieval_eval import GOLDEN_QUESTIONS, run_retrieval_eval

SPOT_CHECK_QUESTIONS = [
    "Show me an anti-dandruff shampoo formula.",
    "Give me a hand cream formula for normal skin.",
]


def _check_llm_response(question: str) -> list[str]:
    errors: list[str] = []
    payload = ChatTurnRequest(thread_id="eval", message=question)
    response = run_chat_pipeline(payload)
    chunks = search(question, top_k=10)

    if not response.llm_used:
        structured = response.structured_formulations or (
            [response.structured_formulation] if response.structured_formulation else []
        )
        if not structured:
            errors.append(f"{question!r}: non-LLM route but no structured_formulation(s)")
            return errors
        if not response.assistant_message.strip():
            errors.append(f"{question!r}: empty assistant_message on template route")
        top = structured[0]
        if "hand cream" in question.lower() and "baby" in top.name.lower():
            errors.append(f"{question!r}: hand cream query returned {top.name!r}")
        if "anti" in question.lower() and "dandruff" in question.lower():
            if "dandruff" not in top.name.lower().replace("-", ""):
                errors.append(f"{question!r}: anti-dandruff query returned {top.name!r}")
        if len(top.ingredients) < 2:
            errors.append(f"{question!r}: structured result has < 2 ingredients")
        return errors

    for i, ev in enumerate(response.cited_evidence):
        if not ev.quote:
            errors.append(f"{question!r}: empty quote on citation {i}")
            continue
        matched = False
        for chunk in chunks:
            if quote_in_chunk(ev.quote, chunk.text):
                matched = True
                if ev.pdf_page and ev.pdf_page != chunk.pdf_page:
                    errors.append(
                        f"{question!r}: pdf_page mismatch cited={ev.pdf_page} chunk={chunk.pdf_page}"
                    )
                break
        if not matched and chunks:
            errors.append(f"{question!r}: quote not found in any retrieved chunk: {ev.quote[:60]}...")

    for pct in extract_percentages(response.assistant_message):
        in_cited = any(pct in c.text for c in chunks)
        if not in_cited:
            errors.append(f"{question!r}: percentage {pct!r} not in retrieved chunks")

    if not response.cited_evidence and "cannot" not in response.assistant_message.lower():
        errors.append(f"{question!r}: no citations but answer did not abstain")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Golden eval. Default: retrieval-only (free). Use --with-llm for full pipeline."
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Run full LLM pipeline + quote/%% validation (costs OpenRouter credits)",
    )
    parser.add_argument(
        "--llm-spot-check",
        type=int,
        metavar="N",
        default=0,
        help="Run LLM checks on the first N questions only",
    )
    parser.add_argument(
        "--spot-check-queries",
        action="store_true",
        help="LLM spot-check anti-dandruff + hand cream only (2 questions)",
    )
    parser.add_argument(
        "--routing-only",
        action="store_true",
        help="Run routing/structured golden only (no retrieval table, no LLM)",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Retrieval top-k")
    parser.add_argument("--score-floor", type=float, default=0.35, help="Retrieval score floor")
    args = parser.parse_args()

    all_errors: list[str] = []

    if args.routing_only:
        from scripts.eval_routing import main as routing_main

        return routing_main()
    elif not args.spot_check_queries:
        print("=== Retrieval checks (no LLM) ===")
        retrieval_results = run_retrieval_eval(
            GOLDEN_QUESTIONS,
            top_k=args.top_k,
            score_floor=args.score_floor,
            verbose=True,
        )
        for r in retrieval_results:
            all_errors.extend(f"{r.question}: {e}" for e in r.errors)

    if args.spot_check_queries:
        llm_questions = SPOT_CHECK_QUESTIONS
    elif args.with_llm:
        llm_questions = GOLDEN_QUESTIONS
    elif args.llm_spot_check > 0:
        llm_questions = GOLDEN_QUESTIONS[: args.llm_spot_check]
    else:
        llm_questions = []

    if llm_questions:
        print(f"\n=== LLM checks ({len(llm_questions)} question(s), uses API credits) ===")
        for q in llm_questions:
            print(f"Evaluating LLM: {q}")
            try:
                errs = _check_llm_response(q)
                if errs:
                    all_errors.extend(errs)
                    for e in errs:
                        print(f"  FAIL: {e}")
                else:
                    print("  OK")
            except Exception as exc:
                all_errors.append(f"{q!r}: exception {exc}")
                print(f"  ERROR: {exc}")

    print(f"\n{len(all_errors)} issue(s) total")
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
