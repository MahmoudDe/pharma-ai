from __future__ import annotations

import re

_ING_MARKER = re.compile(
    r"(?:inqredients?|insredients?|puredients?|raw materials|prescription\s+\d)",
    re.I,
)
_REFERENCE = re.compile(
    r"\b(?:"
    r"iodine\s+number|saponification|unsaponified|acid\s+value|"
    r"melting\s+point|eicosenoic\s+acid|linoleic\s+acid|fatty\s+acid\s+component|"
    r"maximum\s+amount\s*\(g\)\s+of\s+ingredient"
    r")\b",
    re.I,
)
_COSMETIC_ING = re.compile(
    r"\b(?:water|glycerin|glycerol|acid|alcohol|wax|oil|surfactant|"
    r"preservative|fragrance|dimethicone|stearate|paraben|citrate)\b",
    re.I,
)
_PRESCRIPTION_HINT = re.compile(r"\bPrescription\s+\d", re.I)


def is_reference_table_block(text: str) -> bool:
    """True for fatty-acid / regulatory tables that are not product formulas."""
    if _ING_MARKER.search(text):
        return False
    if _PRESCRIPTION_HINT.search(text):
        return False
    if "[TABLE]" in text:
        if _REFERENCE.search(text):
            return True
        # Broken pipe tables from PDF extraction (few columns, no formula header)
        pipe_rows = [ln for ln in text.splitlines() if "|" in ln]
        if pipe_rows and not _ING_MARKER.search(text) and not _COSMETIC_ING.search(text):
            return True
    if _REFERENCE.search(text) and not _COSMETIC_ING.search(text):
        return True
    if text.count("|") > 12 and not _ING_MARKER.search(text):
        return True
    return False
