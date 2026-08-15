from __future__ import annotations

import re

from app.formulation.schemas import IngredientLine

_JUNK_NAME = re.compile(
    r"^(?:"
    r"ingredients?|inqredients?|raw materials|procedure|formula|formulation|"
    r"shampoos?|creams?|lotions?|cosmetic|toiletry|formulations?|baby products?|"
    r"product types?|starting formulation|wtg|wt%|wtb|recipe|phase [a-z]|"
    r"part [a-z]|sequence|procedure|q\.?\s*s\.?|water,?\s*dye"
    r")$",
    re.I,
)
_PAGE_NOISE = re.compile(
    r"^(?:page|pdf|printed|\d+\s*[-–]\s*\d+|book)\b",
    re.I,
)
_PROCEDURE_AS_NAME = re.compile(
    r"^(?:melt|mix|stir|heat|charge|add|blend|fill)\b",
    re.I,
)
_FORMULATION_REF = re.compile(r"^formulation\s+\d+", re.I)
_ONLY_NUMBERS = re.compile(r"^\d+(?:\.\d+)?\s*%?$")
_TOO_LONG = 80


def is_valid_ingredient_line(line: IngredientLine) -> bool:
    raw = (line.raw_name or "").strip()
    if not raw or len(raw) < 2 or len(raw) > _TOO_LONG:
        return False
    if _JUNK_NAME.match(raw):
        return False
    if _PAGE_NOISE.search(raw):
        return False
    if _PROCEDURE_AS_NAME.match(raw):
        return False
    if _FORMULATION_REF.match(raw):
        return False
    if _ONLY_NUMBERS.match(raw):
        return False
    lower = raw.lower()
    if any(
        needle in lower
        for needle in (
            "starting formula",
            "starting formulation",
            "product types",
            "cosmetic and",
            "toiletry formulations",
        )
    ):
        return False
    if line.amount is not None:
        unit = (line.unit or "%").lower().strip()
        if unit in {"%", "percent", "wt%", "wtg", "w/w"} and line.amount > 100.0:
            if not (line.amount == 100.0 and "qs" in lower):
                return False
        if line.amount < 0:
            return False
        if line.amount > 500 and unit not in {"ppm", "ppb"}:
            return False
    return True


def filter_ingredient_lines(lines: list[IngredientLine]) -> list[IngredientLine]:
    out: list[IngredientLine] = []
    seen: set[str] = set()
    for line in lines:
        if not is_valid_ingredient_line(line):
            continue
        raw = (line.raw_name or "").strip().lower()
        if re.search(r"\([^)]+\)", raw):
            key = raw
        else:
            key = (line.normalized_name or line.raw_name).lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def confidence_from_ingredients(
    lines: list[IngredientLine],
    base: float,
) -> float:
    n = len(lines)
    if n < 2:
        return 0.0
    bonus = min(n, 12) * 0.02
    return min(0.98, base + bonus)
