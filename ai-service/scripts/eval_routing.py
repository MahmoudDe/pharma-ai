#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from app.formulation.search import structured_search
from app.reasoning.router import route_chat
from app.retrieval.intent import classify_query, parse_query_intent
from app.schemas import ChatTurnRequest

GOLDEN_PATH = SCRIPTS_DIR / "golden_routing.json"


def _load_golden() -> list[dict]:
    if not GOLDEN_PATH.is_file():
        return []
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _check_structured(case: dict, message: str) -> list[str]:
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

    top_name = matches[0].record.name
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
    if min_ing is not None and matches:
        top_count = len(matches[0].record.ingredients)
        if top_count < int(min_ing):
            errors.append(
                f"structured top has {top_count} ingredients < {min_ing}"
            )

    must_have_amounts = case.get("structured_must_have_amounts")
    if must_have_amounts and matches:
        top = matches[0].record
        if not any(i.amount is not None for i in top.ingredients):
            errors.append("structured top has no ingredient amounts")

    prefer = case.get("prefer_structured_name_match")
    if prefer and matches:
        if not re.search(prefer, top_name, re.I):
            better = next(
                (m for m in matches if re.search(prefer, m.record.name, re.I)),
                None,
            )
            if better is None:
                errors.append(
                    f"no structured match preferred /{prefer}/; top was {top_name!r}"
                )
            elif better.record.id != matches[0].record.id:
                errors.append(
                    f"preferred match {better.record.name!r} ranked below {top_name!r}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Routing + structured semantic eval.")
    parser.add_argument(
        "--with-reasoning-llm",
        action="store_true",
        help="Run full pipeline for reasoning cases (uses API credits).",
    )
    args = parser.parse_args()

    cases = _load_golden()
    if not cases:
        print(f"No cases in {GOLDEN_PATH}")
        return 1

    passed = 0
    failed = 0
    for case in cases:
        message = case["message"]
        expect_route = case["expect_route"]
        expect_llm = case["expect_llm"]
        errors: list[str] = []

        classification_only = bool(case.get("classification_only"))
        expect_llm = expect_llm
        if case.get("expect_route") == "reasoning" and args.with_reasoning_llm:
            classification_only = False
            expect_llm = True

        if classification_only:
            route = classify_query(message).route
            llm_used = False
        else:
            routed = route_chat(ChatTurnRequest(thread_id="eval", message=message))
            route = routed.response.route
            llm_used = routed.llm_used

        if route != expect_route:
            errors.append(f"route {route} != {expect_route}")
        if not classification_only and llm_used != expect_llm:
            errors.append(f"llm_used {llm_used} != {expect_llm}")

        if expect_route in ("lookup", "compare") and not case.get("classification_only"):
            errors.extend(_check_structured(case, message))

        ok = not errors
        status = "OK" if ok else "FAIL"
        print(f"{status}  route={route} llm={llm_used}  {message[:60]}")
        for err in errors:
            print(f"       {err}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{passed + failed} routing checks passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
