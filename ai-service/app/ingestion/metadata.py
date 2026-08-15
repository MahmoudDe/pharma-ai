from __future__ import annotations

import hashlib
import re

_PRODUCT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("baby", re.compile(r"\bbaby\b", re.I)),
    ("anti_dandruff", re.compile(r"\banti[-\s]?dandruff\b|\bantidandruff\b", re.I)),
    ("shampoo", re.compile(r"\bshampoo\b|\bsham[d]?oo\b", re.I)),
    ("conditioner", re.compile(r"\bcondition(er|ing)\b|\bleave[-\s]?in\b", re.I)),
    ("cream", re.compile(r"\b(hand\s+)?cream\b|\bhand\s+cream\b|\bgel\s+cream\b", re.I)),
    ("lotion", re.compile(r"\blotion\b", re.I)),
    ("soap", re.compile(r"\b(soap|soaD|hand\s+cleaner)\b", re.I)),
    ("sunscreen", re.compile(r"\bsunscreen\b|\bsolar\s+protection\b|\bsuntan\b|\bspf\b", re.I)),
    ("makeup", re.compile(r"\bmake[-\s]?up\b|\blipstick\b|\blip\s+balm\b", re.I)),
    ("deodorant", re.compile(r"\bdeodorant\b|\bantiperspirant\b", re.I)),
    ("cleanser", re.compile(r"\bcleanser\b|\bfacial\s+wash\b|\bcleansing\b", re.I)),
    ("toner", re.compile(r"\btoner\b", re.I)),
    ("gel", re.compile(r"\bgel\b|\bshower\s+(?:gel|bath)\b", re.I)),
]

_SECTION_HEADING = re.compile(
    r"^([A-Z][A-Za-z0-9\s\-/'']{2,60}(?:Shampoo|Sham[Dd]oo|Shamwoo|Cream|Lotion|Formula|Formulation|Products?))\s*$"
)
_EMBEDDED_FORMULA_NAME = re.compile(
    r"(?:^|\n)("
    r"(?:Anti[-\s]?)?[Dd]andruff[^\n]{0,40}?(?:Sham[Dd]oo|Shampoo)|"
    r"Baby\s+Shampoo[^\n]{0,30}|"
    r"Tube[-\s]Dispensed\s+Hand\s+Cream|"
    r"Hand\s+(?:and\s+)?(?:Nail\s+)?Cream[^\n]{0,30}"
    r")",
    re.I,
)
_TEASER_START = re.compile(
    r"\bstarting\s+(formula|formulation)\b",
    re.I,
)
_PROCEDURE_LINE = re.compile(r"^\s*\d*\.?\s*Procedure\s*:", re.I)


def text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def infer_product_types(text: str, section_title: str | None = None) -> list[str]:
    embedded_title = None
    for match in _EMBEDDED_FORMULA_NAME.finditer(text):
        embedded_title = match.group(1).strip()
    title_for_tags = embedded_title or section_title
    combined = f"{title_for_tags or ''}\n{text}"
    tags: list[str] = []
    for name, pattern in _PRODUCT_PATTERNS:
        if pattern.search(combined):
            tags.append(name)
    if embedded_title and re.search(r"sham[d]?oo", embedded_title, re.I):
        if "shampoo" not in tags:
            tags.append("shampoo")
    return tags


def detect_section_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None
    if _SECTION_HEADING.match(stripped):
        return stripped
    if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}\s+(Shampoo|Cream|Lotion)$", stripped):
        return stripped
    return None


def is_teaser_block(text: str) -> bool:
    if not _TEASER_START.search(text):
        return False
    lower = text.lower()
    if "wtg" in lower or re.search(r"\d+\.\d{2}", text):
        return False
    if "%" in text and re.search(r"\d\s*%", text):
        return False
    if re.search(r"\bPart\s+[A-Z]\b", text, re.I):
        return False
    return len(text) < 800


def chunk_type_for(text: str, is_formula: bool) -> str:
    if "[TABLE]" in text:
        return "table"
    if is_formula:
        return "formula"
    return "prose"
