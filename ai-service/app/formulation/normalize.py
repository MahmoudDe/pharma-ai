"""Ingredient name normalization."""
from __future__ import annotations

import re

_ALIASES: dict[str, str] = {
    "sulfochem ea-2": "sodium laureth sulfate blend",
    "sulfochem als": "ammonium lauryl sulfate",
    "veegum": "magnesium aluminum silicate",
    "methocel fym": "hydroxypropyl methylcellulose",
    "purified water": "water",
    "puri fi ed water": "water",
    "aqua": "water",
}

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        import spacy

        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        _nlp = False
    return _nlp


def normalize_ingredient_name(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip())
    if not cleaned:
        return ""
    key = cleaned.lower()
    if key in _ALIASES:
        return _ALIASES[key]
    nlp = _get_nlp()
    if nlp and nlp is not False:
        doc = nlp(cleaned[:200])
        lemmas = [t.lemma_.lower() for t in doc if t.is_alpha and not t.is_stop]
        if lemmas:
            return " ".join(lemmas[:6])
    return key
