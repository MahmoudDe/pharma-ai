"""Shared formula-block detection for ingest and retrieval."""
from __future__ import annotations

import re

_FORMULA_KEYWORDS = re.compile(
    r"\b(ingredient|ingredients|inqredient|raw materials|formula|formulation|procedure|parts|recipe|wt\.?|w/w)\b",
    re.IGNORECASE,
)
_WTB_PATTERN = re.compile(r"\bwt[b$s%]?\b", re.IGNORECASE)
_PART_LETTER_LINE = re.compile(r"^\s*[A-Z]\s+[A-Za-z]", re.MULTILINE)
_NUMERIC_PERCENT = re.compile(r"\d[\d.,]*\s*%")
_WTG_PATTERN = re.compile(r"\bwtg\b", re.IGNORECASE)
_QS_PATTERN = re.compile(r"\bq\.?\s*s\.?\b", re.IGNORECASE)
_PART_SECTION = re.compile(r"\bPart\s+[A-Z]\b", re.IGNORECASE)
_NUMERIC_WEIGHTS = re.compile(r"\b\d+\.\d{2}\b")
_COMPOSITION_CONTEXT = re.compile(
    r"\b(surfactant|anionic|amphoteric|emulsif|preservative|water)\b",
    re.IGNORECASE,
)


def is_formula_chunk(text: str) -> bool:
    if not text or not text.strip():
        return False

    has_keyword = bool(_FORMULA_KEYWORDS.search(text))
    has_percent = "%" in text or bool(_NUMERIC_PERCENT.search(text))
    has_wtg_table = (
        bool(_WTG_PATTERN.search(text)) or bool(_WTB_PATTERN.search(text))
    ) and (bool(_NUMERIC_WEIGHTS.search(text)) or bool(_PART_SECTION.search(text)))
    has_recipe_parts = bool(re.search(r"\bRecipe\s*:", text, re.I)) and bool(
        _PART_LETTER_LINE.search(text)
    )
    has_part_recipe = bool(_PART_SECTION.search(text)) and bool(_NUMERIC_WEIGHTS.search(text))
    has_composition_pct = bool(_NUMERIC_PERCENT.search(text)) and bool(_COMPOSITION_CONTEXT.search(text))

    if has_percent and has_keyword:
        return True
    if has_wtg_table or has_part_recipe or has_recipe_parts:
        return True
    if bool(_QS_PATTERN.search(text)) and bool(_NUMERIC_WEIGHTS.search(text)) and (
        has_keyword or bool(re.search(r"\bRecipe\s*:", text, re.I))
    ):
        return True
    if has_composition_pct:
        return True
    if has_percent and bool(_PART_SECTION.search(text)):
        return True
    if bool(_QS_PATTERN.search(text)) and has_keyword and bool(_NUMERIC_WEIGHTS.search(text)):
        return True
    return False
