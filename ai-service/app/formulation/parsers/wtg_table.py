from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_PART_LINE = re.compile(
    r"^([A-Z])\s+([A-Za-z][A-Za-z0-9\s\-\./']{1,55}?)\s+(\d+(?:\.\d+)?)",
    re.MULTILINE,
)
_WTG_PAIR = re.compile(
    r"([A-Za-z][A-Za-z0-9\s\-\./']{2,50}?)\s+(\d+(?:\.\d+)?)\s*(\d+(?:\.\d+)?)?",
)
_AMOUNT = re.compile(r"^(\d+(?:\.\d+)?)$")
_QS_AMOUNT = re.compile(r"^qs\s+to\s+100", re.I)


def _parse_part_column_block(part_text: str, phase: str | None) -> list[IngredientLine]:
    """Names listed, then wtg/wt%, then numeric amounts on subsequent lines."""
    if not re.search(r"\b(?:wtg|wt%)\b", part_text, re.I):
        return []

    segments = re.split(r"\b(?:wtg|wt%)\b", part_text, maxsplit=1, flags=re.I)
    if len(segments) < 2:
        return []

    name_block, amount_block = segments[0], segments[1]
    names = [
        ln.strip()
        for ln in name_block.splitlines()
        if ln.strip() and re.match(r"^[A-Za-z]", ln.strip())
        and ln.strip().lower() not in {"raw materials", "procedure"}
    ]
    amounts: list[tuple[float | None, str]] = []
    for ln in amount_block.splitlines():
        ln = ln.strip()
        if not ln or ln.lower().startswith("part "):
            continue
        if _QS_AMOUNT.match(ln):
            amounts.append((None, "qs"))
        elif _AMOUNT.match(ln):
            amounts.append((float(ln), "wtg"))

    lines: list[IngredientLine] = []
    for name, (amount, unit) in zip(names, amounts):
        lines.append(
            IngredientLine(
                raw_name=name,
                normalized_name=normalize_ingredient_name(name),
                amount=amount,
                unit=unit,
                phase=phase,
            )
        )
    return lines


def parse_wtg_table(text: str) -> list[IngredientLine]:
    if "wtg" not in text.lower() and "wt%" not in text.lower() and not re.search(
        r"\bPart\s+[A-Z]\b", text, re.I
    ):
        return []

    lines: list[IngredientLine] = []
    seen: set[str] = set()

    part_splits = re.split(r"(Part\s+[A-Z0-9]\s*:)", text, flags=re.I)
    if len(part_splits) > 1:
        i = 1
        while i < len(part_splits):
            header = part_splits[i]
            body = part_splits[i + 1] if i + 1 < len(part_splits) else ""
            phase_match = re.match(r"Part\s+([A-Z0-9])\s*:", header, re.I)
            phase = phase_match.group(1) if phase_match else None
            for line in _parse_part_column_block(body, phase):
                key = line.normalized_name or line.raw_name
                if key not in seen:
                    seen.add(key)
                    lines.append(line)
            i += 2

    if len(lines) >= 2:
        return lines

    column_lines = _parse_part_column_block(text, None)
    for line in column_lines:
        key = line.normalized_name or line.raw_name
        if key not in seen:
            seen.add(key)
            lines.append(line)

    if len(lines) >= 2:
        return lines

    current_phase: str | None = None
    for raw_line in text.splitlines():
        phase_match = re.match(r"^\s*Part\s+([A-Z0-9])\s*:", raw_line, re.I)
        if phase_match:
            current_phase = phase_match.group(1)
            continue
        match = _PART_LINE.match(raw_line.strip())
        if match:
            phase, name, amount = match.group(1), match.group(2).strip(), float(match.group(3))
            norm = normalize_ingredient_name(name)
            if norm in seen:
                continue
            seen.add(norm)
            lines.append(
                IngredientLine(
                    raw_name=name,
                    normalized_name=norm,
                    amount=amount,
                    unit="wtg",
                    phase=phase,
                )
            )

    if len(lines) >= 2:
        return lines

    for match in _WTG_PAIR.finditer(text):
        name = match.group(1).strip()
        if len(name) < 3 or name.lower() in {"wtg", "wt%", "procedure", "raw materials"}:
            continue
        amount = float(match.group(2))
        norm = normalize_ingredient_name(name)
        if norm in seen:
            continue
        seen.add(norm)
        lines.append(
            IngredientLine(
                raw_name=name,
                normalized_name=norm,
                amount=amount,
                unit="wtg",
                phase=current_phase,
            )
        )

    return lines
