"""Extract structured signals from user queries for retrieval and routing."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_PRODUCT_SUFFIX = (
    r"Cream|Lotion|Shampoo|Conditioner|Gel|Stick|Sunscreen|"
    r"Formulation|Concentrate|Balm|Serum|Mask|Wash|Cleanser"
)

_NAMED_FORMULA = re.compile(
    rf"\b(?:the\s+)?([A-Z][\w\s\-]{{0,60}}?(?:{_PRODUCT_SUFFIX}))\b"
)
_COMPARE_PAIR = re.compile(
    rf"(?:compare|comparison|difference between)\s+(?:the\s+)?(.+?)\s+and\s+(?:the\s+)?(.+?)"
    rf"(?:\s*[\.\?,]|\s+how|\s+what|\s+in terms|\s*$)",
    re.I,
)
_FORMULATION_OF = re.compile(
    rf"\bformulation of (?:the\s+)?([A-Z][\w\s\-]{{0,60}}?(?:{_PRODUCT_SUFFIX}))\b",
    re.I,
)
_INGREDIENT_CHEM = re.compile(
    r"\b("
    r"SPF\s*\d+"
    r"|Carbopol\s+[\w]+"
    r"|Benzophenone-\d+"
    r"|Octyl\s+[\w\s]+"
    r"|Titanium\s+Dioxide"
    r"|Propylene\s+Glycol"
    r"|Glyceryl\s+Stearate"
    r"|PEG-\d+\s+Stearate"
    r"|Xanthan\s+Gum"
    r"|Dimethicone"
    r"|Squalane"
    r"|Disodium\s+EDTA"
    r"|Polawax\s+[\w\d]+"
    r"|Methylparaben|Propylparaben"
    r"|Butylene\s+Glycol"
    r"|Sodium\s+Laureth\s+Sulfate"
    r"|Polysorbate-\d+"
    r")\b",
    re.I,
)
_CONTAINS_BOTH = re.compile(
    r"\bcontains?\s+both\s+(.+?)\s+and\s+(.+?)(?:[\.\?,]|$|\s+what|\s+how)",
    re.I,
)
_ROLE_QUESTION = re.compile(
    r"\b(?:role|function|significance|purpose)\s+of\b|"
    r"\bwhy\s+is\b|\bexplain\s+the\s+role\b|"
    r"\btrade-?offs?\b|\bwhat\s+are\s+the\s+functions?\b|"
    r"\bdiscuss\s+the\b",
    re.I,
)
_IDENTIFY_WITH = re.compile(
    r"\bidentify\b.*\bcontains?\b|\bfind\b.*\bcontains?\b|\bthat\s+uses?\s+both\b",
    re.I,
)

_SKIP_NAME_FRAGMENTS = frozenset(
    {
        "compare",
        "comparison",
        "formulation",
        "formulations",
        "ingredient",
        "ingredients",
        "moisturizing facial",
        "solar protection",
    }
)


@dataclass(slots=True)
class QuerySignals:
    named_formulas: list[str] = field(default_factory=list)
    compare_targets: list[str] = field(default_factory=list)
    required_ingredients: list[str] = field(default_factory=list)
    asks_ingredient_role: bool = False
    asks_identify_with_ingredients: bool = False


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw.strip(" .,;:?"))
    name = re.sub(r"^(?:the|a|an)\s+", "", name, flags=re.I)
    if len(name) < 4:
        return ""
    lower = name.lower()
    if lower in _SKIP_NAME_FRAGMENTS:
        return ""
    return name[:80]


def _dedupe_ci(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract_query_signals(query: str) -> QuerySignals:
    q = query.strip()
    if not q:
        return QuerySignals()

    named: list[str] = []
    compare_targets: list[str] = []

    pair = _COMPARE_PAIR.search(q)
    if pair:
        a, b = _clean_name(pair.group(1)), _clean_name(pair.group(2))
        if a:
            compare_targets.append(a)
        if b:
            compare_targets.append(b)

    for m in _FORMULATION_OF.finditer(q):
        name = _clean_name(m.group(1))
        if name:
            named.append(name)

    for m in _NAMED_FORMULA.finditer(q):
        name = _clean_name(m.group(1))
        if name and name not in named:
            named.append(name)

    required: list[str] = []
    for m in _INGREDIENT_CHEM.finditer(q):
        required.append(m.group(1).strip())

    both = _CONTAINS_BOTH.search(q)
    if both:
        required.append(both.group(1).strip())
        required.append(both.group(2).strip())

    return QuerySignals(
        named_formulas=_dedupe_ci(named),
        compare_targets=_dedupe_ci(compare_targets),
        required_ingredients=_dedupe_ci(required),
        asks_ingredient_role=bool(_ROLE_QUESTION.search(q)),
        asks_identify_with_ingredients=bool(_IDENTIFY_WITH.search(q)),
    )


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def fuzzy_name_match(query_name: str, record_name: str) -> bool:
    qn = normalize_for_match(query_name)
    rn = normalize_for_match(record_name)
    if not qn or not rn:
        return False
    if qn in rn or rn in qn:
        return True
    q_tokens = set(re.findall(r"[a-z]{3,}", query_name.lower()))
    r_tokens = set(re.findall(r"[a-z]{3,}", record_name.lower()))
    if not q_tokens:
        return False
    overlap = len(q_tokens & r_tokens) / len(q_tokens)
    return overlap >= 0.55


def record_has_ingredient(record, needle: str) -> bool:
    n = needle.lower().strip()
    if not n:
        return False
    for ing in record.ingredients:
        raw = (ing.raw_name or "").lower()
        norm = (ing.normalized_name or "").lower()
        if n in raw or n in norm:
            return True
        if n.replace(" ", "") in raw.replace(" ", ""):
            return True
    source = (getattr(record, "source_text", None) or "").lower()
    return n in source


def record_matches_signals(record, signals: QuerySignals) -> bool:
    """True when top structured result satisfies explicit query constraints."""
    if signals.required_ingredients:
        if not all(record_has_ingredient(record, ing) for ing in signals.required_ingredients):
            return False
    if signals.named_formulas and len(signals.named_formulas) == 1:
        if not fuzzy_name_match(signals.named_formulas[0], record.name):
            if not fuzzy_name_match(signals.named_formulas[0], record.source_text[:200]):
                return False
    return True
