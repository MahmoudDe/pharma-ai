#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.ingest_quality import audit_ingest_quality
from app.formulation.search import structured_search
from app.reasoning.router import route_chat
from app.retrieval.intent import classify_query, parse_query_intent
from app.schemas import ChatTurnRequest
from scripts.retrieval_eval import GOLDEN_QUESTIONS, run_retrieval_eval

GOLDEN_ROUTING = SCRIPTS / "golden_routing.json"
GOLDEN_PRODUCT = SCRIPTS / "golden_product.json"


def _load_json_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else []


def _check_structured_product(case: dict, message: str) -> list[str]:
    """Structured search must return complete, on-topic formulas for lookup/compare."""
    errors: list[str] = []
    intent = parse_query_intent(message)
    result = structured_search(message, intent, limit=5)
    matches = result.matches

    min_conf = case.get("min_structured_confidence")
    if min_conf is not None and result.top_confidence < float(min_conf):
        errors.append(
            f"structured confidence {result.top_confidence:.0f} < {min_conf}"
        )

    min_matches = case.get("min_structured_matches")
    if min_matches is not None and len(matches) < int(min_matches):
        errors.append(f"structured matches {len(matches)} < {min_matches}")

    if not matches:
        return errors

    top = matches[0].record
    top_name = top.name

    must_match = case.get("structured_top_name_must_match")
    if must_match and not re.search(must_match, top_name, re.I):
        errors.append(
            f"structured top name {top_name!r} does not match /{must_match}/"
        )

    for forbidden in case.get("structured_top_name_must_not_contain") or []:
        if forbidden.lower() in top_name.lower():
            errors.append(
                f"structured top name {top_name!r} contains forbidden {forbidden!r}"
            )

    min_ing = case.get("min_structured_ingredients")
    if min_ing is not None and len(top.ingredients) < int(min_ing):
        errors.append(
            f"structured top has {len(top.ingredients)} ingredients < {min_ing}"
        )

    must_have_amounts = case.get("structured_must_have_amounts")
    if must_have_amounts and not any(i.amount is not None for i in top.ingredients):
        errors.append("structured top has no ingredient amounts")

    return errors


def _run_routing_product(cases: list[dict]) -> tuple[int, int, list[str]]:
    passed = 0
    failed = 0
    errors: list[str] = []

    for case in cases:
        message = case["message"]
        expect_route = case["expect_route"]
        expect_llm = case["expect_llm"]
        case_errors: list[str] = []

        if case.get("classification_only"):
            route = classify_query(message).route
            llm_used = False
        else:
            routed = route_chat(ChatTurnRequest(thread_id="eval-product", message=message))
            route = routed.response.route
            llm_used = routed.llm_used

        if route != expect_route:
            case_errors.append(f"route {route} != {expect_route}")
        if not case.get("classification_only") and llm_used != expect_llm:
            case_errors.append(f"llm_used {llm_used} != {expect_llm}")

        if expect_route in ("lookup", "compare") and not case.get("classification_only"):
            case_errors.extend(_check_structured_product(case, message))

        label = "OK" if not case_errors else "FAIL"
        print(f"  {label}  route={route} llm={llm_used}  {message[:55]}")
        for err in case_errors:
            print(f"         {err}")
            errors.append(f"{message}: {err}")

        if case_errors:
            failed += 1
        else:
            passed += 1

    return passed, failed, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run product-promise evals (ingest + retrieval + routing). No LLM cost."
    )
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-routing", action="store_true")
    parser.add_argument(
        "--ingest-report-only",
        action="store_true",
        help="Show ingest metrics without failing on thresholds",
    )
    args = parser.parse_args()

    all_errors: list[str] = []

    if not args.skip_ingest:
        print("=== Ingest / parser quality (formulations.db) ===")
        ingest = audit_ingest_quality()
        print(
            f"  {ingest.total_formulas} formulas | "
            f">=6 ing {ingest.share_6plus_ingredients:.0%} | "
            f"amounts {ingest.share_with_amounts:.0%} | "
            f"median {ingest.median_ingredients:.1f} ing"
        )
        if ingest.failures and not args.ingest_report_only:
            for err in ingest.failures:
                print(f"  FAIL: {err}")
                all_errors.append(f"ingest: {err}")
        elif ingest.failures:
            for err in ingest.failures:
                print(f"  note: {err}")
        else:
            print("  OK")

    if not args.skip_retrieval:
        print("\n=== Retrieval (golden questions, vector + BM25) ===")
        results = run_retrieval_eval(GOLDEN_QUESTIONS, verbose=False)
        retrieval_failures = 0
        for r in results:
            if r.errors:
                retrieval_failures += 1
                for err in r.errors:
                    print(f"  FAIL {r.question[:50]}: {err}")
                    all_errors.append(f"retrieval: {r.question}: {err}")
        if retrieval_failures == 0:
            print(f"  OK ({len(results)} questions)")
        else:
            print(f"  {retrieval_failures}/{len(results)} failed")

    if not args.skip_routing:
        cases = _load_json_list(GOLDEN_PRODUCT) or _load_json_list(GOLDEN_ROUTING)
        print(f"\n=== Product routing + structured formulas ({len(cases)} cases) ===")
        if not cases:
            print("  SKIP: no golden_product.json or golden_routing.json")
        else:
            passed, failed, routing_errors = _run_routing_product(cases)
            all_errors.extend(routing_errors)
            print(f"  {passed}/{passed + failed} passed")

    print(f"\n{len(all_errors)} product-promise issue(s)")
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
