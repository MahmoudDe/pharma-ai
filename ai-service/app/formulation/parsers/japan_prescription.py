"""Parse Japan cosmetics book Prescription tables (Part / Ingredient / % layout)."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_PRESCRIPTION = re.compile(r"\bPrescription\s+(\d+(?:\.\d+)?)", re.I)
_HEADER = re.compile(r"\bPart\b.*\bIngredient\b.*%", re.I | re.S)
_ROW_NUM = re.compile(r"^\d+\s*$")
_PHASE = re.compile(r"^[A-Z]\s*$")
_AMOUNT = re.compile(r"^(\d+(?:\.\d+)?|to\s+100(?:\.\d+)?(?:\s*g)?)\s*$", re.I)
_SKIP = re.compile(
    r"^(?:Directions|Specifications|Part|Ingredient|%|pH:|The |Almost |Generally )\b",
    re.I,
)


def _parse_amount_token(raw: str) -> tuple[float | None, str]:
    s = raw.strip().lower()
    if s.startswith("to 100"):
        # "to 100" is a quantum-satis fill, not an amount of 100
        return None, "qs"
    m = re.match(r"^(\d+(?:\.\d+)?)", raw.strip())
    if m:
        return float(m.group(1)), "%"
    return None, "%"


def parse_japan_prescription(text: str) -> list[IngredientLine]:
    if not _PRESCRIPTION.search(text) and not _HEADER.search(text):
        return []

    lines_out: list[IngredientLine] = []
    seen: set[str] = set()
    current_phase: str | None = None
    pending_parts: list[str] = []
    in_table = False

    def flush_name_with_amount(amount_line: str) -> None:
        nonlocal pending_parts, current_phase
        if not pending_parts:
            return
        name = " ".join(pending_parts).strip()
        pending_parts = []
        if len(name) < 2 or _SKIP.match(name):
            return
        amount, unit = _parse_amount_token(amount_line)
        norm = normalize_ingredient_name(name)
        if norm in seen:
            return
        seen.add(norm)
        lines_out.append(
            IngredientLine(
                raw_name=name,
                normalized_name=norm,
                amount=amount,
                unit=unit,
                phase=current_phase,
            )
        )

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _PRESCRIPTION.search(stripped) or _HEADER.search(stripped):
            in_table = True
            continue
        if not in_table:
            continue
        if _SKIP.match(stripped):
            if lines_out:
                break
            continue
        if _ROW_NUM.match(stripped):
            continue
        if _PHASE.match(stripped):
            if pending_parts:
                pending_parts = []
            current_phase = stripped
            continue
        if _AMOUNT.match(stripped):
            flush_name_with_amount(stripped)
            continue
        if re.match(r"^[A-Za-z0-9]", stripped):
            pending_parts.append(stripped)

    return lines_out
