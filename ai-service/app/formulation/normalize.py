from __future__ import annotations

import re

# Arabic script — use warehouse.arabic_aliases, not English normalization
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

_ALIASES: dict[str, str] = {
    "sulfochem ea-2": "sodium laureth sulfate",
    "sulfochem als": "ammonium lauryl sulfate",
    "sulfochem b-209": "sodium laureth sulfate",
    "sles": "sodium laureth sulfate",
    "sls": "sodium lauryl sulfate",
    "sodium lauryl sulfate": "sodium lauryl sulfate",
    "sodium laureth sulfate": "sodium laureth sulfate",
    "capb": "cocamidopropyl betaine",
    "cocamidopropyl betaine": "cocamidopropyl betaine",
    "veegum": "magnesium aluminum silicate",
    "methocel fym": "hydroxypropyl methylcellulose",
    "methocel f4m": "hydroxypropyl methylcellulose",
    "methocel f4 m": "hydroxypropyl methylcellulose",
    "methyl paraben": "methylparaben",
    "methylparaben": "methylparaben",
    "triethanolamine": "triethanolamine",
    "tea": "triethanolamine",
    "carbomer": "carbomer",
    "carbopol": "carbomer",
    "glycerin": "glycerin",
    "glycerine": "glycerin",
    "propylene glycol": "propylene glycol",
    "purified water": "water",
    "puri fi ed water": "water",
    "deionized water": "water",
    "aqua": "water",
    "fragrance": "fragrance",
    "parfum": "fragrance",
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
    if re.search(r"[\u0600-\u06FF]", cleaned):
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
