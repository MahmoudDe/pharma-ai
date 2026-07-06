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

GENERATE_SYSTEM = """You create evaluation questions for a cosmetic/pharmaceutical formulation RAG assistant.
Questions must be answerable from the provided book passages (formulas, ingredients, procedures, surfactant notes).
Return JSON only with this shape:
{
  "questions": [
    {
      "id": "q01",
      "question": "...",
      "category": "lookup|compare|reasoning|ingredient_knowledge",
      "product_types": ["shampoo"],
      "must_mention_any": ["optional substring hints from passages"],
      "must_not_mention": ["off-topic products to penalize"]
    }
  ]
}
Rules:
- Exactly the requested number of questions.
- Mix categories: ~40% lookup, ~20% compare, ~20% reasoning, ~20% ingredient_knowledge.
- Use realistic phrasing a formulator would ask.
- Ground each question in the passages; do not invent product names not supported by passages.
- NEVER reference "Passage N" or passage numbers in questions — use formula names, product types, or ingredients from the text.
- Vary product types: shampoo, baby, anti-dandruff, cream, lotion, conditioner, etc. when present in passages.
- must_mention_any: substrings a correct answer should include (from real passage text, not passage labels).
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate book-grounded eval questions via OpenRouter.")
    parser.add_argument("-n", "--count", type=int, default=50, help="Number of questions")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="Overwrite existing output file")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"Output exists: {args.output} (use --force to regenerate)")
        return 0

    excerpts = gather_book_excerpts()
    if len(excerpts) < 5:
        print("Not enough corpus excerpts — run ingestion first (run_ingest).", file=sys.stderr)
        return 1

    passage_block = format_excerpts_for_prompt(excerpts)
    user = (
        f"Generate exactly {args.count} evaluation questions from these passages:\n\n"
        f"{passage_block}\n\n"
        f"Use ids q01..q{args.count:02d}."
    )

    print(f"Generating {args.count} questions with OpenRouter model={eval_model_name()} ...")
    data = chat_json(system=GENERATE_SYSTEM, user=user)
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
        cleaned.append(item)

    payload = {
        "version": 1,
        "count": len(cleaned),
        "model": eval_model_name(),
        "passage_count": len(excerpts),
        "questions": cleaned,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(payload['questions'])} questions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
