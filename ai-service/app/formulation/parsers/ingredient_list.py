"""Parse line-based ingredient lists without percentages."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_LIST_LINE = re.compile(
    r"^[\s•\-]*([A-Za-z][A-Za-z0-9\s\-\./']{2,50})(?:\s+\d|$)",
    re.MULTILINE,
)
_INGREDIENTS_HEADER = re.compile(
    r"\b(?:inqredients?|insredients?|ingredients?|raw materials)\s*:",
    re.I,
)


def parse_ingredient_list(text: str) -> list[IngredientLine]:
    if not _INGREDIENTS_HEADER.search(text) and "Ingredients:" not in text:
        colon_lists = re.findall(
            r"(?:Ingredients?|Inqredients?):\s*([^\n]+(?:\n[A-Z][^\n]+)*)",
            text,
            re.I,
        )
        if not colon_lists:
            return []
        text = "\n".join(colon_lists)

    lines: list[IngredientLine] = []
    seen: set[str] = set()
    for match in _LIST_LINE.finditer(text):
        raw = match.group(1).strip()
        if raw.lower() in {"water", "fragrance", "preservative", "etc"} or len(raw) < 3:
            continue
        norm = normalize_ingredient_name(raw)
        if norm in seen:
            continue
        seen.add(norm)
        lines.append(
            IngredientLine(
                raw_name=raw,
                normalized_name=norm,
                amount=None,
                unit=None,
            )
        )
    return lines
