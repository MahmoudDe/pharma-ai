from __future__ import annotations

import re
from dataclasses import dataclass, field

_PRODUCT_SUFFIX = (
    r"Cream|Lotion|Shampoo|Conditioner|Gel|Stick|Sunscreen|"
    r"Formulation|Concentrate|Balm|Serum|Mask|Wash|Cleanser|Toner|Soap"
)

_NAMED_PRODUCT = (
    rf"(?:[A-Z][\w'/]*(?:[-\s]+[A-Za-z][\w'/-]*){{0,5}})\s+(?:{_PRODUCT_SUFFIX})"
)
_NAMED_FORMULA = re.compile(rf"\b({_NAMED_PRODUCT})\b")
_COMPARE_PRODUCTS = re.compile(
    rf"(?:compare|comparison|difference(?:\s+between)?|vs\.?|versus)"
    rf".{{0,100}}?"
    rf"(?:the\s+)?({_NAMED_PRODUCT})"
    rf".{{0,60}}?\band\b.{{0,24}}?"
    rf"(?:the\s+)?({_NAMED_PRODUCT})",
    re.I,
)
# Fallback: “… in the X Cream and the Y Lotion”
_IN_THE_PAIR = re.compile(
    rf"\b(?:in|of|between|for)\s+(?:the\s+)?"
    rf"({_NAMED_PRODUCT})"
    rf"\s+and\s+(?:the\s+)?"
    rf"({_NAMED_PRODUCT})",
    re.I,
)
_FORMULATION_OF = re.compile(
    rf"\bformulation of (?:the\s+)?"
    rf"((?:[A-Z][\w'/]*(?:[-\s]+[A-Za-z][\w'/-]*){{0,5}})\s+(?:{_PRODUCT_SUFFIX})|conditioner|shampoo|cream|lotion)\b",
    re.I,
)
_INGREDIENT_CHEM = re.compile(
    r"\b("
    r"SPF\s*\d+"
    r"|Carbopol\s+[\w]+"
    r"|Benzophenone-\d+"
    r"|Octyl\s+(?:Methoxy\s*)?Cinnamate"
    r"|Octyl\s+Salicylate"
    r"|Titanium\s+Dioxide"
    r"|Zinc\s+Oxide"
    r"|Propylene\s+Glycol"
    r"|Glyceryl\s+Stearate"
    r"|PEG-\d+\s+Stearate"
    r"|Xanthan\s+Gum"
    r"|Dimethicone"
    r"|Squalane"
    r"|Disodium\s+EDTA"
    r"|Polawax\s+[\w\d]*"
    r"|Methylparaben|Propylparaben"
    r"|Butylene\s+Glycol"
    r"|Sodium\s+Laureth\s+Sulfate"
    r"|Cocamidopropyl\s+Betaine|CAPB"
    r"|Polysorbate-\d+"
    r"|Cetearyl\s+Alcohol"
    r"|Cetanol"
    r"|Sorbitan\s+Monostearate"
    r"|Glycerin|Glycerine"
    r")\b",
    re.I,
)
_CONTAINS_BOTH = re.compile(
    r"\b(?:contains?|uses?|with|including|utilizes?)\s+both\s+(.+?)\s+and\s+(.+?)(?:[\.\?,]|$|\s+what|\s+how|\s+as\b)",
    re.I,
)
_CONTAINS_AND = re.compile(
    r"\b(?:contains?|uses?|including|utilizes?)\s+(.+?)\s+and\s+(.+?)(?:\s+as\b|\s+at\b|[\.\?,]|$)",
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
    r"\bidentify\b.*\bcontains?\b|\bfind\b.*\bcontains?\b|\bthat\s+uses?\s+both\b|"
    r"\bidentify\s+a\b|\blotion\s+that\s+contains?\b|\bcream\s+that\s+contains?\b",
    re.I,
)
_ADVICE_QUESTION = re.compile(
    r"(?:"
    r"\bis\s+(?:this|it|the)\b.{0,48}\b(?:suitable|safe|okay|ok|appropriate|intended|meant)\b|"
    r"\b(?:suitable|safe|appropriate)\s+for\s+(?:use\s+)?(?:on\s+)?(?:all\s+)?"
    r"(?:body(?:\s+parts)?|skin|face|hands?|eyes?|everywhere)\b|"
    r"\bcan\s+(?:i|we)\s+(?:use|apply)\b|"
    r"\bis\s+it\s+(?:safe|ok|okay)\s+to\s+(?:use|apply)\b|"
    r"\bshould\s+(?:i|we)\s+use\b|"
    r"\bwhere\s+(?:can|should)\s+(?:i|we)\s+(?:use|apply)\b|"
    r"\bfor\s+all\s+(?:body\s+parts|parts\s+of\s+the\s+body)\b|"
    r"هل\s+يصلح|يصلح\s+(?:هذا|له|ل)|للاستخدام|لكل\s+أعضاء|مناسب\s+(?:ل|لل)"
    r")",
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
        "emulsifiers",
        "surfactants",
        "preservatives",
        "thickening agents",
        "oil phases",
        "oil content",
    }
)
_BAD_NAME_PREFIX = re.compile(
    r"^(?:compare|comparison|explain|discuss|identify|what|why|how|role|function|"
    r"significance|purpose|glycol|emulsifiers?|surfactants?|preservatives?|"
    r"used in|differences? in)\b",
    re.I,
)


@dataclass(slots=True)
class QuerySignals:
    named_formulas: list[str] = field(default_factory=list)
    compare_targets: list[str] = field(default_factory=list)
    required_ingredients: list[str] = field(default_factory=list)
    asks_ingredient_role: bool = False
    asks_identify_with_ingredients: bool = False
    asks_advice: bool = False


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw.strip(" .,;:?"))
    name = re.sub(r"^(?:the|a|an)\s+", "", name, flags=re.I)
    # Strip leading junk like "emulsifiers used in the Anti-Acne Cream"
    m = re.search(
        rf"\b((?:[A-Z][\w'/]*(?:[-\s]+[A-Za-z][\w'/-]*){{0,5}})\s+(?:{_PRODUCT_SUFFIX}))\s*$",
        name,
    )
    if m:
        name = m.group(1).strip()
    if len(name) < 4:
        return ""
    lower = name.lower()
    if lower in _SKIP_NAME_FRAGMENTS:
        return ""
    if _BAD_NAME_PREFIX.search(name) and not re.search(
        rf"\b(?:{_PRODUCT_SUFFIX})\b", name, re.I
    ):
        return ""
    if _BAD_NAME_PREFIX.search(name) and len(name.split()) > 6:
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


def _split_ingredient_pair(raw: str) -> list[str]:
    parts = re.split(r"\s+and\s+", raw.strip(), maxsplit=1, flags=re.I)
    return [p.strip(" .,;:") for p in parts if p.strip()]


def extract_query_signals(query: str) -> QuerySignals:
    q = query.strip()
    if not q:
        return QuerySignals()

    named: list[str] = []
    compare_targets: list[str] = []

    pair = _COMPARE_PRODUCTS.search(q)
    if not pair and re.search(r"\b(compare|comparison|difference|vs\.?|versus)\b", q, re.I):
        pair = _IN_THE_PAIR.search(q)
    if not pair:
        pair = _IN_THE_PAIR.search(q)
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
            # Prefer product titles, drop sentence-leading false positives.
            if _BAD_NAME_PREFIX.search(name) and not re.match(
                rf"^[A-Z][\w'/]*(?:[-\s]+[A-Z][\w'/-]*)*\s+(?:{_PRODUCT_SUFFIX})$",
                name,
            ):
                continue
            named.append(name)

    # Title-case product phrases even mid-sentence (“the Moisturizing Facial Lotion”)
    for m in re.finditer(
        rf"\b((?:[A-Z][\w'/]*(?:[-\s]+(?:[A-Z][\w'/-]*|[a-z]{{2,12}})){{0,5}})\s+(?:{_PRODUCT_SUFFIX}))\b",
        q,
    ):
        name = _clean_name(m.group(1))
        if name:
            named.append(name)

    required: list[str] = []
    for m in _INGREDIENT_CHEM.finditer(q):
        required.append(m.group(1).strip())

    both = _CONTAINS_BOTH.search(q)
    if both:
        required.extend(_split_ingredient_pair(both.group(1)))
        required.extend(_split_ingredient_pair(both.group(2)))
    elif _CONTAINS_AND.search(q) and not required:
        m = _CONTAINS_AND.search(q)
        assert m is not None
        for part in (m.group(1), m.group(2)):
            chem = _INGREDIENT_CHEM.search(part)
            if chem:
                required.append(chem.group(1).strip())
            elif 3 <= len(part.strip()) <= 40:
                required.append(part.strip())

    # Drop compound "A and B" leftovers if both sides already present.
    cleaned_ings: list[str] = []
    for ing in required:
        if " and " in ing.lower():
            continue
        cleaned_ings.append(ing)

    named = _dedupe_ci(named)
    compare_targets = _dedupe_ci(compare_targets)
    # Named formulas that are also compare targets stay in compare list.
    if compare_targets:
        named = [n for n in named if n.lower() not in {c.lower() for c in compare_targets}]

    return QuerySignals(
        named_formulas=named,
        compare_targets=compare_targets,
        required_ingredients=_dedupe_ci(cleaned_ings),
        asks_ingredient_role=bool(_ROLE_QUESTION.search(q)),
        asks_identify_with_ingredients=bool(_IDENTIFY_WITH.search(q)),
        asks_advice=bool(_ADVICE_QUESTION.search(q)),
    )


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


_GENERIC_NAME_TOKENS = frozenset(
    {
        "cream",
        "lotion",
        "shampoo",
        "conditioner",
        "gel",
        "formula",
        "formulation",
        "product",
        "products",
        "skin",
        "hair",
        "body",
        "facial",
        "moisturizing",
        "moisturising",
        "moisturizins",
        "moisturizina",
        "moisturisins",
        "liquid",
    }
)


def _fold_ocr(text: str) -> str:
    """Normalize common OCR typos in book titles (Moisturizins → moisturizing)."""
    t = text.lower()
    replacements = (
        ("moisturizins", "moisturizing"),
        ("moisturizina", "moisturizing"),
        ("moisturisins", "moisturizing"),
        ("moisturixins", "moisturizing"),
        ("moisturising", "moisturizing"),
        ("liahteninu", "lightening"),
        ("shamdoo", "shampoo"),
        ("shamwoo", "shampoo"),
        ("conditionina", "conditioning"),
        ("usins", "using"),
    )
    for a, b in replacements:
        t = t.replace(a, b)
    return t


def fuzzy_name_match(query_name: str, record_name: str) -> bool:
    q_fold = _fold_ocr(query_name)
    r_fold = _fold_ocr(record_name)
    qn = normalize_for_match(q_fold)
    rn = normalize_for_match(r_fold)
    if not qn or not rn:
        return False
    if qn == rn:
        return True
    if (qn in rn or rn in qn) and min(len(qn), len(rn)) >= 12:
        return True
    q_tokens = set(re.findall(r"[a-z]{3,}", q_fold))
    r_tokens = set(re.findall(r"[a-z]{3,}", r_fold))
    if not q_tokens:
        return False
    # Keep product form words, but require non-generic anchors when present.
    soft_generic = {"cream", "lotion", "shampoo", "conditioner", "gel", "formula", "formulation"}
    distinctive = q_tokens - soft_generic - {
        "product",
        "products",
        "skin",
        "hair",
        "body",
        "liquid",
    }
    if distinctive and not (distinctive & r_tokens):
        return False
    overlap = len(q_tokens & r_tokens) / len(q_tokens)
    if len(distinctive) >= 2:
        return overlap >= 0.7 and len(distinctive & r_tokens) >= 2
    if distinctive:
        return overlap >= 0.65 and bool(distinctive & r_tokens)
    return q_tokens <= r_tokens and len(q_tokens) >= 2


def record_has_ingredient(record, needle: str) -> bool:
    n = needle.lower().strip()
    if not n:
        return False
    blob = f"{record.name}\n{getattr(record, 'source_text', '') or ''}".lower()
    # SPF must match the number when provided (avoid SPF 15 counting as SPF 24).
    if n.startswith("spf"):
        digits = re.search(r"\d+", n)
        if digits:
            return bool(re.search(rf"\bspf\s*{digits.group(0)}\b", blob, re.I))
        return bool(re.search(r"\bspf\b", blob, re.I))

    for ing in record.ingredients:
        raw = (ing.raw_name or "").lower()
        norm = (ing.normalized_name or "").lower()
        if n in raw or n in norm:
            return True
        if n.replace(" ", "") in raw.replace(" ", "") or n.replace(" ", "") in norm.replace(" ", ""):
            return True
        n_toks = set(re.findall(r"[a-z0-9]{3,}", n))
        r_toks = set(re.findall(r"[a-z0-9]{3,}", f"{raw} {norm}"))
        if n_toks and len(n_toks & r_toks) / len(n_toks) >= 0.75:
            return True
    # Multi-token chem names: require most tokens in source, not a single fragment.
    n_toks = [t for t in re.findall(r"[a-z0-9]{3,}", n) if t not in {"the", "and"}]
    if len(n_toks) >= 2:
        hits = sum(1 for t in n_toks if t in blob)
        return hits >= max(2, len(n_toks) - 1)
    if len(n) >= 5 and n in blob:
        return True
    return False


def record_matches_signals(record, signals: QuerySignals) -> bool:
    """True when top structured result satisfies explicit query constraints."""
    if signals.required_ingredients:
        if not all(record_has_ingredient(record, ing) for ing in signals.required_ingredients):
            return False
    titles = signals.named_formulas or signals.compare_targets
    if titles and len(titles) == 1:
        if not fuzzy_name_match(titles[0], record.name):
            if not fuzzy_name_match(titles[0], record.source_text[:240]):
                return False
    return True
