#!/usr/bin/env python3
"""Generate evaluation questions from ingested book content via OpenRouter."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.corpus_samples import gather_book_excerpts, format_excerpts_for_prompt
from app.eval.openrouter_client import chat_json, eval_model_name

DEFAULT_OUT = Path(__file__).resolve().parent / "generated_book_questions.json"
DEFAULT_HARD_OUT = Path(__file__).resolve().parent / "generated_hard_questions.json"

_JSON_SHAPE = """{
  "questions": [
    {
      "id": "q01",
      "question": "...",
      "category": "lookup|compare|reasoning|ingredient_knowledge",
      "difficulty": "standard|hard",
      "product_types": ["shampoo"],
      "must_mention_any": ["optional substring hints from passages"],
      "must_not_mention": ["off-topic products to penalize"]
    }
  ]
}"""

_COMMON_RULES = """
- Exactly the requested number of questions.
- Use realistic phrasing a formulator would ask.
- Ground each question in the passages; do not invent product names not supported by passages.
- NEVER reference "Passage N" or passage numbers in questions — use formula names, product types, or ingredients from the text.
- must_mention_any: substrings a correct answer should include (from real passage text, not passage labels).
- must_not_mention: common wrong product types the assistant might confuse (baby cream for hand cream, etc.).
"""

GENERATE_SYSTEM = f"""You create evaluation questions for a cosmetic/pharmaceutical formulation RAG assistant.
Questions must be answerable from the provided book passages (formulas, ingredients, procedures, surfactant notes).
Return JSON only with this shape:
{_JSON_SHAPE}
Rules:
{_COMMON_RULES}
- Mix categories: ~40% lookup, ~20% compare, ~20% reasoning, ~20% ingredient_knowledge.
- Vary product types: shampoo, baby, anti-dandruff, cream, lotion, conditioner, etc. when present in passages.
- Set difficulty to "standard" for all questions.
"""

HARD_GENERATE_SYSTEM = f"""You create HARD evaluation questions for a cosmetic formulation RAG assistant.
These questions should stress-test retrieval, product-type disambiguation, and grounded answers.
Return JSON only with this shape:
{_JSON_SHAPE}
Rules:
{_COMMON_RULES}
- Set difficulty to "hard" for every question.
- Mix categories: ~35% lookup, ~25% compare, ~25% reasoning, ~15% ingredient_knowledge.
- Make questions genuinely difficult:
  * Lookup: ask for a specific formula type WITH constraints (e.g. baby + mild surfactant, hand cream not baby cream, anti-dandruff with named actives).
  * Compare: compare two formulas from passages on ingredients, phases, or surfactant choices — name both products.
  * Reasoning: ask why an ingredient or surfactant is used, tradeoffs (SLS vs CAPB, emulsifier choice), or procedure rationale.
  * Ingredient knowledge: ask about function, typical use level, or compatibility — only if passage supports it.
- Require answers to cite specific ingredients, percentages, or procedure steps from the books when passages include them.
- Include must_not_mention for plausible confusions (wrong product category, wrong book formula).
- Avoid trivial one-word answers; prefer questions where a wrong retrieval path would produce a plausible but wrong formula.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate book-grounded eval questions via OpenRouter.")
    parser.add_argument("-n", "--count", type=int, default=50, help="Number of questions")
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument(
        "--hard",
        action="store_true",
        help="Generate stress-test questions (writes generated_hard_questions.json by default)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="Overwrite existing output file")
    args = parser.parse_args()

    output = args.output or (DEFAULT_HARD_OUT if args.hard else DEFAULT_OUT)

    if output.exists() and not args.force:
        print(f"Output exists: {output} (use --force to regenerate)")
        return 0

    excerpts = gather_book_excerpts()
    if len(excerpts) < 5:
        print("Not enough corpus excerpts — run ingestion first (run_ingest).", file=sys.stderr)
        return 1

    passage_block = format_excerpts_for_prompt(excerpts)
    system = HARD_GENERATE_SYSTEM if args.hard else GENERATE_SYSTEM
    difficulty_label = "hard" if args.hard else "standard"
    user = (
        f"Generate exactly {args.count} {difficulty_label} evaluation questions from these passages:\n\n"
        f"{passage_block}\n\n"
        f"Use ids q01..q{args.count:02d}."
    )

    print(
        f"Generating {args.count} {difficulty_label} questions "
        f"with OpenRouter model={eval_model_name()} ..."
    )
    data = chat_json(system=system, user=user)
    questions = data.get("questions") or data.get("items") or []
    if not isinstance(questions, list):
        print("Unexpected response shape from OpenRouter", file=sys.stderr)
        return 1

    if len(questions) < args.count:
        print(f"Warning: got {len(questions)} questions, requested {args.count}")

    passage_ref = re.compile(r"\bpassage\s+\d+\b", re.I)
    cleaned: list[dict] = []
    for item in questions[: args.count]:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", ""))
        if passage_ref.search(q):
            q = passage_ref.sub("", q).replace("  ", " ").strip(" ,?")
            item = {**item, "question": q}
        if args.hard:
            item = {**item, "difficulty": "hard"}
        cleaned.append(item)

    payload = {
        "version": 1,
        "count": len(cleaned),
        "difficulty": difficulty_label,
        "model": eval_model_name(),
        "passage_count": len(excerpts),
        "questions": cleaned,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(payload['questions'])} questions to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
