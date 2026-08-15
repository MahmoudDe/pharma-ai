#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.openrouter_client import chat_json, eval_model_name
from app.reasoning.pipeline import run_chat_pipeline
from app.retrieval.search import search
from app.schemas import ChatTurnRequest

DEFAULT_QUESTIONS = Path(__file__).resolve().parent / "generated_book_questions.json"

JUDGE_SYSTEM = """You are a strict evaluator for a cosmetic formulation RAG assistant.
Given a user question, retrieved source passages, and the assistant answer, judge quality.

Return JSON only:
{
  "pass": true,
  "score": 4,
  "grounded": true,
  "relevant": true,
  "issues": ["short issue strings"],
  "reasoning": "one paragraph"
}

Scoring (1-5):
5 = correct, grounded, appropriate formula/knowledge for the question
3 = partially correct or thin but usable
1 = wrong product type, hallucinated ingredients, or ignores sources

pass=true only if score>=4, grounded=true, relevant=true, and no major issues.
Penalize: wrong product (baby cream for hand cream), invented percentages, ignoring passages.
Reward: structured formula with ingredients when question asks for a formula.
"""


@dataclass
class EvalCase:
    question: str
    case_id: str = ""
    category: str = ""
    must_mention_any: list[str] = field(default_factory=list)
    must_not_mention: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    case: EvalCase
    pass_: bool
    score: float
    issues: list[str]
    route: str = ""
    llm_used: bool = False
    judge_reasoning: str = ""


def _load_cases(path: Path, limit: int | None) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("questions", raw) if isinstance(raw, dict) else raw
    cases: list[EvalCase] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", "")).strip()
        if not q:
            continue
        cases.append(
            EvalCase(
                question=q,
                case_id=str(item.get("id", f"q{i+1:02d}")),
                category=str(item.get("category", "")),
                must_mention_any=list(item.get("must_mention_any") or []),
                must_not_mention=list(item.get("must_not_mention") or []),
            )
        )
        if limit and len(cases) >= limit:
            break
    return cases


def _format_structured(response) -> str:
    parts: list[str] = [response.assistant_message or ""]
    structured = response.structured_formulations or (
        [response.structured_formulation] if response.structured_formulation else []
    )
    for sf in structured[:3]:
        lines = [f"Structured: {sf.name} ({len(sf.ingredients)} ingredients)"]
        for ing in (sf.ingredients or [])[:10]:
            amt = ""
            if ing.get("amount") is not None:
                amt = f" {ing['amount']}{' ' + (ing.get('unit') or '') if ing.get('unit') else ''}"
            lines.append(f"  - {ing.get('raw_name', '')}{amt}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _judge_case(case: EvalCase, answer_text: str, sources: list[str]) -> dict:
    source_block = "\n\n".join(f"[SOURCE {i+1}]\n{s[:900]}" for i, s in enumerate(sources[:6]))
    hints = ""
    if case.must_mention_any:
        hints += f"\nExpected to mention any of: {case.must_mention_any}"
    if case.must_not_mention:
        hints += f"\nMust NOT mention: {case.must_not_mention}"

    user = (
        f"QUESTION ({case.category or 'general'}):\n{case.question}\n\n"
        f"RETRIEVED SOURCES:\n{source_block}\n\n"
        f"ASSISTANT ANSWER:\n{answer_text}\n"
        f"{hints}"
    )
    return chat_json(system=JUDGE_SYSTEM, user=user)


def _rule_checks(case: EvalCase, answer_text: str) -> list[str]:
    errors: list[str] = []
    lower = answer_text.lower()
    for needle in case.must_not_mention:
        if needle.lower() in lower:
            errors.append(f"forbidden phrase {needle!r} in answer")
    if case.must_mention_any:
        if not any(n.lower() in lower for n in case.must_mention_any):
            errors.append(f"expected one of {case.must_mention_any}")
    return errors


def evaluate_case(case: EvalCase) -> EvalResult:
    payload = ChatTurnRequest(thread_id=f"eval-{case.case_id}", message=case.question)
    response = run_chat_pipeline(payload)
    chunks = search(case.question, top_k=8)
    answer_text = _format_structured(response)
    sources = [c.combined_text() for c in chunks]

    judge = _judge_case(case, answer_text, sources)
    rule_errors = _rule_checks(case, answer_text)

    score = float(judge.get("score", 0))
    pass_ = bool(judge.get("pass")) and not rule_errors
    issues = list(judge.get("issues") or []) + rule_errors

    return EvalResult(
        case=case,
        pass_=pass_,
        score=score,
        issues=issues,
        route=response.route,
        llm_used=response.llm_used,
        judge_reasoning=str(judge.get("reasoning", "")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run OpenRouter LLM judge eval on generated book questions."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS,
        help="JSON file from generate_book_questions.py",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max questions (0 = all)")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON results here")
    args = parser.parse_args()

    if not args.questions.is_file():
        print(
            f"Questions file not found: {args.questions}\n"
            "Run: .venv/bin/python scripts/generate_book_questions.py",
            file=sys.stderr,
        )
        return 1

    limit = args.limit or None
    cases = _load_cases(args.questions, limit)
    if not cases:
        print("No questions loaded.", file=sys.stderr)
        return 1

    print(f"OpenRouter judge eval: {len(cases)} question(s), judge model={eval_model_name()}")
    results: list[EvalResult] = []
    passed = 0

    for i, case in enumerate(cases, start=1):
        print(f"\n[{i}/{len(cases)}] {case.case_id}: {case.question[:70]}...")
        try:
            result = evaluate_case(case)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append(
                EvalResult(
                    case=case,
                    pass_=False,
                    score=0.0,
                    issues=[str(exc)],
                )
            )
            continue

        status = "PASS" if result.pass_ else "FAIL"
        print(f"  {status} score={result.score:.1f} route={result.route} llm={result.llm_used}")
        for issue in result.issues[:4]:
            print(f"    - {issue}")
        if result.pass_:
            passed += 1
        results.append(result)

    print(f"\n{passed}/{len(cases)} passed (OpenRouter judge)")

    if args.output:
        out = {
            "judge_model": eval_model_name(),
            "passed": passed,
            "total": len(cases),
            "results": [
                {
                    "id": r.case.case_id,
                    "question": r.case.question,
                    "pass": r.pass_,
                    "score": r.score,
                    "route": r.route,
                    "llm_used": r.llm_used,
                    "issues": r.issues,
                    "reasoning": r.judge_reasoning,
                }
                for r in results
            ],
        }
        args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.output}")

    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
