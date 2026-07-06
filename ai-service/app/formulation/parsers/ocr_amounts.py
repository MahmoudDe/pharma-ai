"""Normalize OCR-spaced numeric amount lines before parsing."""
from __future__ import annotations

import re

_OCR_NUMERIC = re.compile(r"^[\d\s.\-]+$")

# A dot with whitespace on at least one side, between digits on the same line:
# "5 . 0" / "0 .5" / "1. 0" -> joined.
_SPACED_DOT = re.compile(r"(?<=\d)(?:[ \t]+\.[ \t]*|[ \t]*\.[ \t]+)(?=\d)")
# Line that is purely a spaced decimal fragment: "5.0 0", "2.0 0 0".
_NUMERIC_DOT_LINE = re.compile(r"^[\d. \t]*\.[\d. \t]*$")
_SINGLE_NUMBER = re.compile(r"^\d+\.\d*$")
# Table cell where OCR dropped the decimal point: "52 00" means 52.00.
_DROPPED_DOT_CELL = re.compile(r"^(\d+)[ \t]+(\d{1,2})$")
_QS_CELL = re.compile(r"^q[\s.]*s[\s.]*$", re.IGNORECASE)


def repair_spaced_decimals(text: str) -> str:
    """Fix OCR-spaced decimals before parsing: ``5 . 0 0`` -> ``5.00``.

    Conservative on purpose: dots are only joined when digits flank them on
    the same line, and trailing digit fragments are merged only on lines that
    contain nothing but the number.
    """
    repaired = _SPACED_DOT.sub(".", text)
    lines = []
    for line in repaired.splitlines():
        stripped = line.strip()
        if _NUMERIC_DOT_LINE.match(stripped):
            collapsed = re.sub(r"[ \t]+", "", stripped)
            # only when the collapse yields ONE clean decimal — a line with
            # two amounts ("25.0 45.7") must be left alone
            if _SINGLE_NUMBER.match(collapsed):
                lines.append(line.replace(stripped, collapsed))
                continue
        lines.append(line)
    return "\n".join(lines)


def normalize_table_cell_amount(cell: str) -> str:
    """Clean one amount cell from a pipe-separated table row.

    ``52 00`` -> ``52.00`` (OCR-dropped decimal point), ``q s`` -> ``q.s.``,
    ``0 .5-1 .0`` -> ``0.5-1.0``. Returns "" when the cell holds no amount.
    """
    cell = _SPACED_DOT.sub(".", cell.strip()).rstrip(".").strip()
    if not cell:
        return ""
    if _QS_CELL.match(cell):
        return "q.s."
    if re.match(r"^to\s+100", cell, re.I):
        return "to 100"
    if "-" in cell:
        parts = [normalize_table_cell_amount(p) for p in cell.split("-", 1)]
        if all(re.match(r"^\d+(?:\.\d+)?$", p) for p in parts):
            return "-".join(parts)
    dropped = _DROPPED_DOT_CELL.match(cell)
    if dropped:
        return f"{dropped.group(1)}.{dropped.group(2)}"
    if re.match(r"^\d+(?:\.\d+)?$", cell):
        return cell
    return ""


def normalize_ocr_amount_line(line: str) -> str:
    """Collapse OCR spacing: ``1 6 . 4`` -> ``16.4``, ``8 . 0 0`` -> ``8.00``."""
    stripped = line.strip()
    if not stripped:
        return stripped

    lower = re.sub(r"\s+", "", stripped.lower())
    if lower in {"qs", "q.s.", "q.s"} or lower.startswith("qsto"):
        return "q.s."
    if re.match(r"^to\s+100", stripped, re.I):
        return "to 100"

    if "-" in stripped and _OCR_NUMERIC.match(stripped.replace(" ", "")):
        head = stripped.split("-", 1)[0].strip()
        return normalize_ocr_amount_line(head)

    if not re.search(r"\d", stripped):
        return stripped

    compact = re.sub(r"\s+", "", stripped)
    if re.match(r"^\d+\.?\d*$", compact):
        return compact

    dot_match = re.match(r"^([\d\s]+)\.([\d\s]+)$", stripped)
    if dot_match:
        whole = re.sub(r"\s+", "", dot_match.group(1))
        frac = re.sub(r"\s+", "", dot_match.group(2))
        return f"{whole}.{frac}"

    spaced_dot = re.match(r"^([\d\s]+)\s+\.\s+([\d\s]+)$", stripped)
    if spaced_dot:
        whole = re.sub(r"\s+", "", spaced_dot.group(1))
        frac = re.sub(r"\s+", "", spaced_dot.group(2))
        return f"{whole}.{frac}"

    return re.sub(r"(?<=\d)\s+(?=\d)", "", stripped)
