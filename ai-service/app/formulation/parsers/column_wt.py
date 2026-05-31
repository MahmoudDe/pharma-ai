"""Parse Volume-8 column layouts: ingredient names then wt% amounts (or reverse)."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_ING_HEADER = re.compile(
    r"(?:inqredients?|insredients?|ingredients?|raw materials)\s*:",
    re.I,
)
_WT_MARKER = re.compile(r"^\s*(?:Wt[%\$]|wt%)\s*$", re.I)
_NAME_LINE = re.compile(
    r"^[A-Za-z][A-Za-z0-9\s\-\./',\(\)&]+$"
)
_AMOUNT_LINE = re.compile(
    r"^("
    r"to\s+100(?:\.\d+)?"
    r"|qs(?:\s+to\s+100(?:\.\d+)?)?"
    r"|q\s*\.?\s*s\s*\.?"
    r"|\d+(?:\.\d+)?"
    r")\s*\.?\s*$",
    re.I,
)
_SKIP_NAME = re.compile(
    r"^(?:procedure|blending procedure|formulation no|source|note)\b",
    re.I,
)
_FORMULA_SECTION = re.compile(
    r"\n(?=(?:Baby|Anti|Hand|Tube|Clear|Natural)\s+[^\n]{2,70}\s*\n|"
    r"\nShampoo\s*\n\s*Starting\s+formulation)",
    re.I,
)


def _parse_amount_token(raw: str) -> tuple[float | None, str]:
    s = re.sub(r"\s+", "", raw.strip().lower())
    if re.match(r"^q\.?s\.?$", s) or s.startswith("qs"):
        return None, "qs"
    if s.startswith("to100"):
        return 100.0, "wt%"
    m = re.match(r"^(\d+(?:\.\d+)?)", raw.strip())
    if m:
        return float(m.group(1)), "wt%"
    return None, "wt%"


def _collect_names(block: str) -> list[str]:
    names: list[str] = []
    in_names = False
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _ING_HEADER.search(stripped):
            in_names = True
            continue
        if not in_names:
            continue
        if _WT_MARKER.match(stripped):
            break
        if _AMOUNT_LINE.match(stripped):
            break
        if _SKIP_NAME.match(stripped):
            break
        if not _NAME_LINE.match(stripped) or len(stripped) < 3:
            continue
        lower = stripped.lower()
        if lower in {"water", "fragrance"} or "preservative" in lower:
            names.append(stripped)
            continue
        if any(
            needle in lower
            for needle in (
                "starting formula",
                "starting formulation",
                "cosmetic and",
                "toiletry formulations",
            )
        ):
            continue
        names.append(stripped)
    return names


def _collect_amounts(block: str) -> list[tuple[float | None, str]]:
    amounts: list[tuple[float | None, str]] = []
    in_amounts = False
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _WT_MARKER.match(stripped):
            in_amounts = True
            continue
        if _ING_HEADER.search(stripped):
            continue
        if not in_amounts and _AMOUNT_LINE.match(stripped):
            in_amounts = True
        if not in_amounts:
            continue
        if _SKIP_NAME.match(stripped) or _ING_HEADER.search(stripped):
            break
        if _AMOUNT_LINE.match(stripped):
            amounts.append(_parse_amount_token(stripped))
        elif _NAME_LINE.match(stripped) and amounts:
            break
    return amounts


def _pair_names_amounts(
    names: list[str],
    amounts: list[tuple[float | None, str]],
) -> list[IngredientLine]:
    if len(names) < 2 or len(amounts) < 2:
        return []
    n = min(len(names), len(amounts))
    lines: list[IngredientLine] = []
    seen: set[str] = set()
    for name, (amount, unit) in zip(names[:n], amounts[:n]):
        norm = normalize_ingredient_name(name)
        if norm in seen:
            continue
        seen.add(norm)
        lines.append(
            IngredientLine(
                raw_name=name,
                normalized_name=norm,
                amount=amount,
                unit=unit,
            )
        )
    return lines


def _parse_names_then_amounts(text: str) -> list[IngredientLine]:
    if not _ING_HEADER.search(text):
        return []
    names = _collect_names(text)
    amounts = _collect_amounts(text)
    return _pair_names_amounts(names, amounts)


def _parse_amounts_then_names(text: str) -> list[IngredientLine]:
    if not _ING_HEADER.search(text) or not re.search(r"\bwt[%\$]\s*", text, re.I):
        return []

    best: list[IngredientLine] = []
    for wt_match in re.finditer(r"\b(?:wt%|wt\$)\s*", text, flags=re.I):
        tail = text[wt_match.end() :]
        amount_lines: list[str] = []
        name_lines: list[str] = []
        phase = "amounts"
        for line in tail.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _ING_HEADER.search(stripped):
                phase = "names"
                continue
            if phase == "amounts":
                if _AMOUNT_LINE.match(stripped):
                    amount_lines.append(stripped)
                elif _NAME_LINE.match(stripped) and not amount_lines:
                    phase = "names"
                    name_lines.append(stripped)
            else:
                if _SKIP_NAME.match(stripped):
                    break
                if _NAME_LINE.match(stripped):
                    name_lines.append(stripped)
                elif _WT_MARKER.match(stripped):
                    break

        lines = _pair_names_amounts(
            name_lines,
            [_parse_amount_token(a) for a in amount_lines],
        )
        if len(lines) > len(best):
            best = lines
    return best


def parse_column_wt_layout(text: str) -> list[IngredientLine]:
    if not re.search(r"\b(?:wt%|wt\$)\s*", text, re.I) and not _ING_HEADER.search(text):
        return []

    sections = _FORMULA_SECTION.split(text) if _ING_HEADER.search(text) else [text]
    best: list[IngredientLine] = []
    for section in sections:
        if not section.strip():
            continue
        for parser in (_parse_names_then_amounts, _parse_amounts_then_names):
            lines = parser(section)
            if len(lines) > len(best):
                best = lines
    return best
