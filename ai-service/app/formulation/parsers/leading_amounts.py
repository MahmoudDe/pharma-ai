from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.parsers.ocr_amounts import normalize_ocr_amount_line
from app.formulation.schemas import IngredientLine

_WT_MARKER = re.compile(r"^\s*wt\s*[%\$8]\s*$", re.I | re.M)
_ING_HEADER = re.compile(r"^(?:in[qg]redients?|insredients?)\s*[:;]\s*$", re.I | re.M)
_AMOUNT_LINE = re.compile(r"^(?:typical:\s*)?(\d+(?:\.\d+)?)\s*$", re.I)
_QS = re.compile(r"^q[\s.]*s[\s.]*$|^(?:ad|to)\s+100", re.I)
_STOP = re.compile(r"^(?:blending|procedure|method|mixing|note|adjust)\b", re.I)


def parse_leading_amounts(text: str) -> list[IngredientLine]:
    wt = _WT_MARKER.search(text)
    header = _ING_HEADER.search(text)
    if not wt or not header or wt.end() > header.start():
        return []

    # amounts between the Wt% marker and the ingredient header
    amounts: list[tuple[float | None, str]] = []
    for raw_line in text[wt.end():header.start()].splitlines():
        stripped = normalize_ocr_amount_line(raw_line.strip())
        if not stripped:
            continue
        match = _AMOUNT_LINE.match(raw_line.strip()) or _AMOUNT_LINE.match(stripped)
        if match:
            amounts.append((float(match.group(1)), "wt%"))
        elif _QS.match(stripped):
            amounts.append((None, "qs"))
        else:
            return []  # prose between marker and header -> not this layout

    if len(amounts) < 2:
        return []

    # names after the header, then any trailing amounts continue the pairing
    names: list[str] = []
    for raw_line in text[header.end():].splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _STOP.match(stripped):
            break
        normalized = normalize_ocr_amount_line(stripped)
        match = _AMOUNT_LINE.match(stripped) or _AMOUNT_LINE.match(normalized)
        if match:
            amounts.append((float(match.group(1)), "wt%"))
        elif _QS.match(normalized):
            amounts.append((None, "qs"))
        elif re.match(r"^[A-Za-z]", stripped):
            names.append(stripped)

    if not names:
        return []

    lines_out: list[IngredientLine] = []
    for name, (amount, unit) in zip(names, amounts):
        lines_out.append(
            IngredientLine(
                raw_name=name,
                normalized_name=normalize_ingredient_name(name),
                amount=amount,
                unit=unit,
            )
        )
    return lines_out
