"""Parse inline wt% rows: name and amount on adjacent lines (Volume 8 concentrate tables)."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.parsers.ocr_amounts import normalize_ocr_amount_line
from app.formulation.schemas import IngredientLine

_WT_HEADER = re.compile(r"^\s*wt[%\$]\s*$", re.I)
_ING_HEADER = re.compile(
    r"^\s*(?:inqredients?|insredients?|raw materials)\s*:?\s*$",
    re.I,
)
_AMOUNT = re.compile(
    r"^\s*("
    r"to\s+100(?:\.\d+)?"
    r"|q\.?\s*s\.?"
    r"|\d+(?:\.\d+)?"
    r")\s*\.?\s*$",
    re.I,
)
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9\s\-\./',\(\)&]+$")
_SKIP = re.compile(
    r"^(?:procedure|blending|typical|formulation|source|starting)\b",
    re.I,
)


def _amount(raw: str) -> tuple[float | None, str]:
    raw = normalize_ocr_amount_line(raw)
    s = re.sub(r"\s+", "", raw.strip().lower())
    if re.match(r"^q\.?s\.?$", s):
        return None, "qs"
    if s.startswith("to100"):
        return 100.0, "wt%"
    m = re.match(r"^(\d+(?:\.\d+)?)", raw.strip())
    if m:
        return float(m.group(1)), "wt%"
    return None, "wt%"


def parse_inline_wt_rows(text: str) -> list[IngredientLine]:
    """Pair ingredient names with wt% amounts from column or stacked inline layouts."""
    if not re.search(r"\bwt[%\$]\s*", text, re.I):
        return []

    best: list[IngredientLine] = []
    for wt_match in re.finditer(r"\bwt[%\$]\s*", text, re.I):
        tail = text[wt_match.end() :]
        amounts: list[tuple[float | None, str]] = []
        names: list[str] = []
        phase: str = "amounts"

        for line in tail.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _SKIP.match(stripped):
                break
            if _ING_HEADER.match(stripped):
                phase = "names"
                continue
            if phase == "amounts":
                normalized = normalize_ocr_amount_line(stripped)
                if _AMOUNT.match(normalized):
                    amounts.append(_amount(stripped))
                elif _NAME.match(stripped) and len(stripped) >= 3:
                    phase = "names"
                    names.append(stripped)
            else:
                if _AMOUNT.match(stripped) and names:
                    break
                if _NAME.match(stripped) and len(stripped) >= 3:
                    names.append(stripped)

        n = min(len(names), len(amounts))
        if n < 2:
            continue
        lines: list[IngredientLine] = []
        seen: set[str] = set()
        for name, (amt, unit) in zip(names[:n], amounts[:n]):
            norm = normalize_ingredient_name(name)
            if norm in seen:
                continue
            seen.add(norm)
            lines.append(
                IngredientLine(
                    raw_name=name,
                    normalized_name=norm,
                    amount=amt,
                    unit=unit,
                )
            )
        if len(lines) > len(best):
            best = lines
    return best
