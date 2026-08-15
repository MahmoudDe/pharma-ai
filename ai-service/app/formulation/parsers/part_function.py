from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_PART_HEADER = re.compile(r"^\s*Part\s+([A-Z0-9])\s*:", re.I)
_FUNCTION_HEADER = re.compile(
    r"(?:inqredients?|insredients?|ingredients?)/function\s*:|inqredient/function\s*:",
    re.I,
)
_AMOUNT = re.compile(
    r"^\s*(\d+(?:\.\d+)?|q\s*\.?\s*s\s*\.?)\s*\.?\s*$",
    re.I,
)
_SKIP = re.compile(
    r"^(?:procedure|typical|formulation no|source|note|wt%|\.whitening)\b",
    re.I,
)


def _clean_name_line(raw: str) -> str:
    line = raw.strip()
    if "/" in line:
        line = line.split("/")[0].strip()
    line = re.sub(r"\s*\[\d+\]\s*", " ", line)
    line = re.sub(r"\(\d+\)", "", line)
    return line.strip()


def _parse_amount(raw: str) -> tuple[float | None, str]:
    s = re.sub(r"\s+", "", raw.strip().lower())
    if re.match(r"^q\.?s\.?$", s):
        return None, "qs"
    m = re.match(r"^(\d+(?:\.\d+)?)", raw.strip())
    if m:
        return float(m.group(1)), "wt%"
    return None, "wt%"


def parse_part_function_layout(text: str) -> list[IngredientLine]:
    if not _FUNCTION_HEADER.search(text) and not _PART_HEADER.search(text):
        return []

    lines: list[IngredientLine] = []
    seen: set[str] = set()
    current_phase: str | None = None
    pending_names: list[str] = []
    pending_amounts: list[tuple[float | None, str]] = []

    def flush_part() -> None:
        nonlocal pending_names, pending_amounts
        n = min(len(pending_names), len(pending_amounts))
        for name, (amount, unit) in zip(pending_names[:n], pending_amounts[:n]):
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
                    phase=current_phase,
                )
            )
        pending_names = []
        pending_amounts = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or _SKIP.match(stripped):
            if pending_names and pending_amounts:
                flush_part()
            continue

        part_match = _PART_HEADER.match(stripped)
        if part_match:
            if pending_names and pending_amounts:
                flush_part()
            current_phase = part_match.group(1).upper()
            continue

        if _FUNCTION_HEADER.search(stripped):
            continue

        if _AMOUNT.match(stripped):
            pending_amounts.append(_parse_amount(stripped))
            continue

        if re.match(r"^[A-Za-z]", stripped) and not stripped.endswith("%"):
            name = _clean_name_line(stripped)
            if len(name) >= 3 and not _SKIP.match(name):
                pending_names.append(name)

    if pending_names and pending_amounts:
        flush_part()

    return lines
