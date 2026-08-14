"""Shared retrieval-only evaluation helpers (no LLM / no API credits)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.retrieval.search import RetrievedChunk, is_formula_chunk, search

GOLDEN_QUESTIONS = [
    "Give me a baby shampoo formula with ingredient percentages.",
    "What surfactants are commonly used in shampoo formulations?",
    "Show me an anti-dandruff shampoo formula.",
    "Give me a hand cream formula for normal skin.",
    "Compare baby shampoo formulas with mild surfactants.",
    "I need a sulfate-free shampoo formulation.",
    "Show me a conditioning shampoo formula.",
    "Give me a body lotion formula with humectants.",
]

_FORMULA_INTENT = re.compile(
    r"\b(formula|formulation|ingredient|percentage|%|shampoo|cream|lotion)\b",
    re.IGNORECASE,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_GOLDEN_PATH = SCRIPTS_DIR / "golden_retrieval.json"


@dataclass
class GoldenExpectation:
    min_formula_in_top_k: int | None = None
    top_k: int = 5
    doc_title_contains: list[str] = field(default_factory=list)
    product_types_any: list[str] = field(default_factory=list)
    product_types_all: list[str] = field(default_factory=list)
    min_top_score: float | None = None
    combined_text_must_match: str | None = None
    combined_text_must_not_contain: list[str] = field(default_factory=list)
    min_ingredient_count: int | None = None


@dataclass
class RetrievalEvalResult:
    question: str
    errors: list[str] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)


def load_golden_questions(path: Path | None = None) -> list[str]:
    golden_path = path or DEFAULT_GOLDEN_PATH
    if not golden_path.is_file():
        return list(GOLDEN_QUESTIONS)
    raw: dict[str, Any] = json.loads(golden_path.read_text(encoding="utf-8"))
    return list(raw.keys())


def load_golden_expectations(path: Path | None = None) -> dict[str, GoldenExpectation]:
    golden_path = path or DEFAULT_GOLDEN_PATH
    if not golden_path.is_file():
        return {}

    raw: dict[str, Any] = json.loads(golden_path.read_text(encoding="utf-8"))
    out: dict[str, GoldenExpectation] = {}
    for question, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        out[question] = GoldenExpectation(
            min_formula_in_top_k=spec.get("min_formula_in_top_k"),
            top_k=int(spec.get("top_k", 5)),
            doc_title_contains=list(spec.get("doc_title_contains") or []),
            product_types_any=list(spec.get("product_types_any") or []),
            product_types_all=list(spec.get("product_types_all") or []),
            min_top_score=spec.get("min_top_score"),
            combined_text_must_match=spec.get("combined_text_must_match"),
            combined_text_must_not_contain=list(spec.get("combined_text_must_not_contain") or []),
            min_ingredient_count=spec.get("min_ingredient_count"),
        )
    return out


def wants_formula_intent(question: str) -> bool:
    return bool(_FORMULA_INTENT.search(question))


def print_chunk_table(chunks: list[RetrievedChunk], *, snippet_len: int = 120) -> None:
    if not chunks:
        print("  (no chunks retrieved)")
        return
    for i, chunk in enumerate(chunks, start=1):
        snippet = chunk.text.replace("\n", " ")[:snippet_len]
        formula = is_formula_chunk(chunk.text)
        printed = chunk.printed_page if chunk.printed_page is not None else "-"
        tags = ",".join(chunk.product_types or []) or "-"
        print(
            f"  {i:2d}  score={chunk.score:.3f}  formula={str(formula):5s}  tags={tags}  "
            f"pdf={chunk.pdf_page}  printed={printed}  {chunk.doc_title!r}"
        )
        print(f"      {snippet}...")


def evaluate_retrieval(
    question: str,
    *,
    top_k: int = 10,
    score_floor: float = 0.35,
    golden: GoldenExpectation | None = None,
) -> RetrievalEvalResult:
    errors: list[str] = []
    chunks = search(question, top_k=top_k)

    if not chunks:
        errors.append("no chunks retrieved")
        return RetrievalEvalResult(question=question, errors=errors, chunks=chunks)

    effective_floor = golden.min_top_score if golden and golden.min_top_score is not None else score_floor
    if chunks[0].score < effective_floor:
        errors.append(f"top-1 score {chunks[0].score:.3f} below floor {effective_floor}")

    asks_for_formula = bool(
        re.search(r"\b(give me|show me|provide|list)\b.*\b(formula|formulation)\b", question, re.I)
        or re.search(r"\bformula\b.*\b(with|including)\b", question, re.I)
    )
    if asks_for_formula:
        top_n = chunks[:3]
        if not any(is_formula_chunk(c.text) for c in top_n):
            errors.append("formula intent: no formula chunk in top-3")

    if golden:
        window = chunks[: golden.top_k]
        if golden.min_formula_in_top_k:
            count = sum(1 for c in window if is_formula_chunk(c.text))
            if count < golden.min_formula_in_top_k:
                errors.append(
                    f"golden: expected >= {golden.min_formula_in_top_k} formula chunk(s) "
                    f"in top-{golden.top_k}, got {count}"
                )
        for needle in golden.doc_title_contains:
            if not any(needle.lower() in c.doc_title.lower() for c in window):
                errors.append(f"golden: no chunk with doc_title containing {needle!r}")
        if golden.product_types_any:
            found = False
            for c in window:
                chunk_tags = set(c.product_types or [])
                if chunk_tags & set(golden.product_types_any):
                    found = True
                    break
            if not found:
                combined_check = any(
                    _chunk_matches_product_types(c, golden.product_types_any) for c in window
                )
                if not combined_check:
                    errors.append(
                        f"golden: no chunk with product_types matching any of {golden.product_types_any}"
                    )
        if golden.product_types_all:
            found_all = any(
                _chunk_matches_product_types(c, golden.product_types_all, require_all=True)
                for c in window
            )
            if not found_all:
                errors.append(
                    f"golden: no chunk with all product_types {golden.product_types_all} in top-{golden.top_k}"
                )

        if golden.combined_text_must_match:
            pattern = re.compile(golden.combined_text_must_match, re.I)
            if not any(pattern.search(_chunk_combined(c)) for c in window):
                errors.append(
                    f"golden: no chunk in top-{golden.top_k} matching /{golden.combined_text_must_match}/"
                )

        for forbidden in golden.combined_text_must_not_contain:
            needle = forbidden.lower()
            for c in window[:3]:
                if needle in _chunk_combined(c).lower():
                    errors.append(
                        f"golden: top-3 chunk contains forbidden phrase {forbidden!r}"
                    )
                    break

        if golden.min_ingredient_count:
            best_count = max((c.ingredient_count or 0) for c in window)
            if best_count < golden.min_ingredient_count:
                errors.append(
                    f"golden: expected top-{golden.top_k} chunk with >= "
                    f"{golden.min_ingredient_count} ingredients, best={best_count}"
                )

    return RetrievalEvalResult(question=question, errors=errors, chunks=chunks)


def _chunk_combined(chunk: RetrievedChunk) -> str:
    return f"{chunk.section_title or ''}\n{chunk.text}"


def _chunk_matches_product_types(
    chunk: RetrievedChunk,
    types: list[str],
    *,
    require_all: bool = False,
) -> bool:
    tags = set(chunk.product_types or [])
    combined = f"{chunk.section_title or ''}\n{chunk.text}".lower()
    if require_all:
        for t in types:
            if t in tags:
                continue
            if t == "anti_dandruff" and re.search(r"anti[-\s]?dandruff|antidandruff", combined, re.I):
                continue
            if t == "baby" and "baby" in combined:
                continue
            if t == "shampoo" and "shampoo" in combined:
                continue
            if t == "cream" and "cream" in combined:
                continue
            return False
        return True
    return bool(tags & set(types))


def run_retrieval_eval(
    questions: list[str] | None = None,
    *,
    top_k: int = 10,
    score_floor: float = 0.35,
    golden_path: Path | None = None,
    verbose: bool = True,
) -> list[RetrievalEvalResult]:
    golden_map = load_golden_expectations(golden_path)
    qs = questions or load_golden_questions(golden_path)
    results: list[RetrievalEvalResult] = []

    for question in qs:
        if verbose:
            print(f"\nEvaluating retrieval: {question}")
        golden = golden_map.get(question)
        result = evaluate_retrieval(
            question,
            top_k=top_k,
            score_floor=score_floor,
            golden=golden,
        )
        results.append(result)
        if verbose:
            print_chunk_table(result.chunks)
            if result.errors:
                for err in result.errors:
                    print(f"  FAIL: {err}")
            else:
                print("  OK")

    return results
