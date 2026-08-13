"""Parse numbered Stage/Material tables (A&E Connock style).

Layout — row index, material name and amount each on their own line:

    Staqe: Material:
    wt%
    Oil Phase:
    1
    Light Mineral Oil
    7.000
    2
    Triethanolamine 99%      <- "99%" is a concentration grade, not the amount
    2.500

The row indices must increment strictly from 1, which makes this parser
near-impossible to trigger by accident.
"""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_HEADER = re.compile(r"sta[gq]e\s*:?\s*material", re.I)
_WT_MARKER = re.compile(r"\bwt\s*[%\$8]", re.I)
_INDEX_LINE = re.compile(r"^\d{1,2}$")
_AMOUNT_LINE = re.compile(r"^(\d+(?:\.\d+)?)$")
_PHASE_LINE = re.compile(r"^([A-Za-z][A-Za-z ]{2,30}?)\s*(?:Phase|Cycle)\s*:$", re.I)
_STOP = re.compile(r"^(?:mixing\s+instructions|procedure|method)\b", re.I)


def parse_numbered_stage(text: str) -> list[IngredientLine]:
    if not _HEADER.search(text) or not _WT_MARKER.search(text):
        return []

    lines_out: list[IngredientLine] = []
    phase: str | None = None
    expected_index = 1
    pending_name: str | None = None
    awaiting_amount = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _STOP.match(stripped):
            break

        phase_match = _PHASE_LINE.match(stripped)
        if phase_match:
            phase = phase_match.group(1).strip()
            continue

        if _INDEX_LINE.match(stripped) and int(stripped) == expected_index:
            expected_index += 1
            pending_name = None
            awaiting_amount = False
            continue

        if awaiting_amount:
            amount_match = _AMOUNT_LINE.match(stripped)
            if amount_match and pending_name:
                amount = float(amount_match.group(1))
                lines_out.append(
                    IngredientLine(
                        raw_name=pending_name,
                        normalized_name=normalize_ingredient_name(pending_name),
                        amount=amount,
                        unit="wt%",
                        phase=phase,
                    )
                )
            pending_name = None
            awaiting_amount = False
            continue

        if expected_index > 1 and pending_name is None and re.match(r"^[A-Za-z]", stripped):
            pending_name = stripped
            awaiting_amount = True

    return lines_out
