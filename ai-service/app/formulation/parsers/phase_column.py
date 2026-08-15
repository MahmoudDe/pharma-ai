from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_PHASE_HEADER = re.compile(r"^Phase\s+([A-Z0-9])\s*:\s*$", re.I | re.M)
_WT_MARKER = re.compile(r"\bwt\s*[%\$8]", re.I)
_AMOUNT_LINE = re.compile(r"^(\d+(?:\.\d+)?)$")
_QS_LINE = re.compile(r"^(?:q\.?\s*s\.?|to\s+100(?:\.\d+)?)$", re.I)
_SKIP_NAME = re.compile(
    r"^(?:in[qgu]redients?|procedure|blending|method|mixing|note)\b", re.I
)


def parse_phase_column(text: str) -> list[IngredientLine]:
    if not _WT_MARKER.search(text):
        return []
    headers = list(_PHASE_HEADER.finditer(text))
    if not headers:
        return []

    lines_out: list[IngredientLine] = []
    for i, header in enumerate(headers):
        phase = header.group(1).upper()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        segment = text[header.end():end]

        names: list[str] = []
        amounts: list[float | None] = []
        for raw_line in segment.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if _SKIP_NAME.match(stripped):
                break
            if _AMOUNT_LINE.match(stripped):
                amounts.append(float(stripped))
            elif _QS_LINE.match(stripped):
                amounts.append(None)
            elif re.match(r"^[A-Za-z]", stripped) and not amounts:
                # names come before the amount column; an alpha line after
                # amounts started means prose — stop this segment
                names.append(stripped)
            else:
                if amounts:
                    break

        if not names or not amounts:
            continue
        for name, amount in zip(names, amounts):
            unit = "wt%" if amount is not None else "qs"
            lines_out.append(
                IngredientLine(
                    raw_name=name,
                    normalized_name=normalize_ingredient_name(name),
                    amount=amount,
                    unit=unit,
                    phase=phase,
                )
            )
    return lines_out
