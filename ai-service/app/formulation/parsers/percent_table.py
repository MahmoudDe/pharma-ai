"""Parse Japan-style Ingredient % tables."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_ROW = re.compile(
    r"^([A-Za-z][A-Za-z0-9\s\-\./']{1,60}?)\s+(\d+(?:\.\d+)?)\s*(%|g)?\s*$",
    re.MULTILINE,
)
_INLINE = re.compile(
    r"([A-Za-z][A-Za-z0-9\s\-\./']{2,40}?)\s+(\d+(?:\.\d+)?)\s*%",
)


def parse_percent_table(text: str) -> list[IngredientLine]:
    if "ingredient" not in text.lower() and "%" not in text:
        return []

    lines: list[IngredientLine] = []
    seen: set[str] = set()

    for pattern in (_ROW, _INLINE):
        for match in pattern.finditer(text):
            raw = match.group(1).strip()
            if len(raw) < 2 or raw.lower() in {"ingredient", "phase", "total"}:
                continue
            amount = float(match.group(2))
            unit = match.group(3) if pattern is _ROW and match.lastindex >= 3 else "%"
            unit = unit or "%"
            norm = normalize_ingredient_name(raw)
            if norm in seen:
                continue
            seen.add(norm)
            lines.append(
                IngredientLine(
                    raw_name=raw,
                    normalized_name=norm,
                    amount=amount,
                    unit=unit,
                )
            )

    return lines
