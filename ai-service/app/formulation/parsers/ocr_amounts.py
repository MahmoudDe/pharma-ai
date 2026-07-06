"""Normalize OCR-spaced numeric amount lines before parsing."""
from __future__ import annotations

import re

_OCR_NUMERIC = re.compile(r"^[\d\s.\-]+$")


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
