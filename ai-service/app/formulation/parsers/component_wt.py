from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import IngredientLine

_HEADER = re.compile(r"^Components?\s*:\s*$", re.I | re.M)
_WT_MARKER = re.compile(r"^\s*wt\s*[%\$8]\s*$", re.I | re.M)
_AMOUNT_LINE = re.compile(r"^(\d+(?:\.\d+)?)\s*$")
_AD_100 = re.compile(r"^(?:ad|to)\s+100(?:\.\d+)?$", re.I)
_QS = re.compile(r"^q[\s.]*s[\s.]*$", re.I)
_STOP = re.compile(
    r"^(?:pH\s+Value|Procedure|Preparation|Mix\b|Formulation\s+No|Viscosity|Note)\b", re.I
)


def parse_component_wt(text: str) -> list[IngredientLine]:
    if not _HEADER.search(text) or not _WT_MARKER.search(text):
        return []

    marker = _WT_MARKER.search(text)
    body = text[marker.end():]

    lines_out: list[IngredientLine] = []
    pending: list[str] = []

    def flush(amount: float | None, unit: str) -> None:
        nonlocal pending
        if not pending:
            return
        # rejoin OCR-hyphenated wraps: "Metho- sulfate" -> "Methosulfate"
        name = " ".join(pending).replace("- ", "").strip()
        pending = []
        if len(name) < 2:
            return
        if len(name) > 78:  # keep within the shared ingredient-name filter limit
            name = name[:78].rsplit(" ", 1)[0].rstrip(" ,;(")
        lines_out.append(
            IngredientLine(
                raw_name=name,
                normalized_name=normalize_ingredient_name(name),
                amount=amount,
                unit=unit,
            )
        )

    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _STOP.match(stripped):
            break
        if _AMOUNT_LINE.match(stripped):
            flush(float(stripped), "wt%")
            continue
        if _AD_100.match(stripped) or _QS.match(stripped):
            flush(None, "qs")
            continue
        if re.match(r"^[A-Za-z]", stripped):
            pending.append(stripped)

    return lines_out
