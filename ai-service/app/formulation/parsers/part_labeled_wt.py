"""Parse Part A:/B:/C: labeled layouts with wt% (roll-on, deodorant)."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.parsers.ocr_amounts import (
    normalize_ocr_amount_line,
    normalize_table_cell_amount,
)
from app.formulation.schemas import IngredientLine

_ING_HEADER = re.compile(
    r"(?:inqredients?|insredients?|ingredients?|puredients?|raw materials)\s*:",
    re.I,
)
_WT_MARKER = re.compile(r"^\s*(?:Wt[%\$8]|wt%)\s*$", re.I)
_PART_LABEL = re.compile(r"^([A-C])\s*:\s*(.*)$", re.I)
_AMOUNT = re.compile(
    r"^\s*("
    r"to\s+100(?:\.\d+)?"
    r"|q\.?\s*s\.?"
    r"|\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?"
    r")\s*\.?\s*$",
    re.I,
)
_SKIP = re.compile(
    r"^(?:procedure|mix\b|pigments?|fragrances?|regulated|desired)\b",
    re.I,
)


def _parse_amount(raw: str) -> tuple[float | None, str]:
    raw = normalize_ocr_amount_line(raw)
    s = raw.strip().lower()
    if re.match(r"^q\.?\s*s\.?$", s) or s.startswith("q"):
        return None, "qs"
    if s.startswith("to 100"):
        return 100.0, "wt%"
    range_m = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*\d", s)
    if range_m:
        return float(range_m.group(1)), "wt%"
    m = re.match(r"^(\d+(?:\.\d+)?)", raw.strip())
    if m:
        return float(m.group(1)), "wt%"
    return None, "wt%"


def _collect_pre_header_amounts(text: str) -> list[tuple[float | None, str]]:
    amounts: list[tuple[float | None, str]] = []
    in_wt = False
    for line in text.splitlines():
        stripped = line.strip()
        if _WT_MARKER.match(stripped):
            in_wt = True
            continue
        if _ING_HEADER.search(stripped):
            break
        if in_wt and _AMOUNT.match(stripped):
            amounts.append(_parse_amount(stripped))
    return amounts


def parse_part_labeled_wt(text: str) -> list[IngredientLine]:
    """Volume-8 roll-on / deodorant blocks with A:/B:/C: phase labels."""
    if not _ING_HEADER.search(text):
        return []
    if not re.search(r"wt\s*[%\$8]", text, re.I):
        return []
    if not re.search(r"\b[A-C]\s*:", text):
        return []

    pre_amounts = _collect_pre_header_amounts(text)
    lines_out: list[IngredientLine] = []
    seen: set[str] = set()
    phase: str | None = None
    pending_names: list[str] = []
    pre_amount_idx = 0
    in_block = False

    def flush_name(name: str, amount: tuple[float | None, str] | None) -> None:
        if not name or len(name) < 2:
            return
        norm = normalize_ingredient_name(name)
        if norm in seen:
            return
        seen.add(norm)
        amt, unit = amount if amount else (None, "wt%")
        lines_out.append(
            IngredientLine(
                raw_name=name,
                normalized_name=norm,
                amount=amt,
                unit=unit,
                phase=phase,
            )
        )

    def pair_pre_amounts(names: list[str]) -> None:
        nonlocal pre_amount_idx
        for name in names:
            amt = pre_amounts[pre_amount_idx] if pre_amount_idx < len(pre_amounts) else None
            if amt:
                pre_amount_idx += 1
            flush_name(name, amt)

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _ING_HEADER.search(stripped):
            in_block = True
            continue
        if not in_block:
            continue

        # Pipe-separated table rows: "A: Wacker-Belsil DMC 6032 | 2 00".
        if "|" in stripped:
            name_part, _, amount_cell = stripped.rpartition("|")
            name_part = name_part.strip()
            cell = normalize_table_cell_amount(amount_cell)
            if not name_part or not cell:
                continue  # prose row or header row, not an ingredient
            part_match = _PART_LABEL.match(name_part)
            if part_match:
                phase = part_match.group(1).upper()
                name_part = (part_match.group(2) or "").strip()
            if pending_names:
                pair_pre_amounts(pending_names)
                pending_names = []
            if not _SKIP.match(name_part):
                flush_name(name_part, _parse_amount(cell))
            continue

        if _SKIP.match(stripped):
            break

        part_match = _PART_LABEL.match(stripped)
        if part_match:
            if pending_names:
                pair_pre_amounts(pending_names)
                pending_names = []
            phase = part_match.group(1).upper()
            inline_name = (part_match.group(2) or "").strip()
            if inline_name and not _AMOUNT.match(inline_name):
                pending_names.append(inline_name)
            continue

        if _AMOUNT.match(stripped):
            amount = _parse_amount(stripped)
            if pending_names:
                flush_name(pending_names.pop(0), amount)
            continue

        if re.match(r"^[A-Za-z]", stripped):
            pending_names.append(stripped)

    if pending_names:
        pair_pre_amounts(pending_names)

    return lines_out
