from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

QueryRoute = Literal["lookup", "compare", "reasoning", "unknown"]

_QUERY_PRODUCT_MAP: list[tuple[str, re.Pattern[str]]] = [
    ("baby", re.compile(r"\bbaby\b", re.I)),
    ("anti_dandruff", re.compile(r"\banti[-\s]?dandruff\b|\bantidandruff\b", re.I)),
    ("shampoo", re.compile(r"\bshampoo\b|\bsham[d]?oo\b", re.I)),
    ("cream", re.compile(r"\b(hand\s+)?cream\b|\bgel\s+cream\b|\bshaving\s+cream\b", re.I)),
    ("lotion", re.compile(r"\blotion\b", re.I)),
    ("conditioner", re.compile(r"\bcondition(er|ing)\b|\bleave[-\s]?in\b", re.I)),
    ("sunscreen", re.compile(r"\bsunscreen\b|\bspf\b|\bsolar\s+protection\b|\bsuntan\b", re.I)),
    ("soap", re.compile(r"\bsoap\b|\bhand\s+cleaner\b", re.I)),
    ("makeup", re.compile(r"\blipstick\b|\bmake[-\s]?up\b|\blip\s+balm\b", re.I)),
    ("deodorant", re.compile(r"\bdeodorant\b|\bantiperspirant\b", re.I)),
    ("cleanser", re.compile(r"\bcleanser\b|\bfacial\s+wash\b|\bfacial\s+cleanser\b", re.I)),
    ("toner", re.compile(r"\btoner\b", re.I)),
    ("gel", re.compile(r"\bshower\s+(?:gel|bath)\b|\b(?:clear\s+)?shampoo\s+gel\b|(?<!cream\s)\bgel\b", re.I)),
]

_REASONING = re.compile(
    r"\b(why|how does|how do|explain|instead of|versus|vs\.|compare benefits|recommend|"
    r"should i use|what happens if|mechanism|difference between .+ and .+ because)\b",
    re.I,
)
# Usage / suitability about a product already in context — not a recipe dump.
_ADVICE = re.compile(
    r"(?:"
    r"\bis\s+(?:this|it|the)\b.{0,48}\b(?:suitable|safe|okay|ok|appropriate|intended|meant)\b|"
    r"\b(?:suitable|safe|appropriate)\s+for\s+(?:use\s+)?(?:on\s+)?(?:all\s+)?"
    r"(?:body(?:\s+parts)?|skin|face|hands?|eyes?|everywhere)\b|"
    r"\bcan\s+(?:i|we)\s+(?:use|apply)\b|"
    r"\bis\s+it\s+(?:safe|ok|okay)\s+to\s+(?:use|apply)\b|"
    r"\bshould\s+(?:i|we)\s+use\b|"
    r"\bwhere\s+(?:can|should)\s+(?:i|we)\s+(?:use|apply)\b|"
    r"\bfor\s+all\s+(?:body\s+parts|parts\s+of\s+the\s+body)\b|"
    r"\ball\s+over\s+(?:the\s+)?body\b|"
    r"هل\s+يصلح|يصلح\s+(?:هذا|له|ل)|للاستخدام|لكل\s+أعضاء|مناسب\s+(?:ل|لل)"
    r")",
    re.I,
)
_COMPARE = re.compile(
    r"\b(compare|comparison|difference between|vs\.?|versus)\b",
    re.I,
)
_LOOKUP = re.compile(
    r"\b(give me|show me|provide|list|get)\b.*\b(formula|formulation|recipe)\b",
    re.I,
)
_VAGUE_BEST = re.compile(r"\bbest\b", re.I)
_ROLE_REASONING = re.compile(
    r"\b(?:role|function|significance|purpose)\s+of\b|"
    r"\bwhy\s+is\b|\bexplain\s+the\s+role\b|"
    r"\btrade-?offs?\b|\bwhat\s+are\s+the\s+functions?\b|"
    r"\bdiscuss\s+the\b",
    re.I,
)


@dataclass(slots=True)
class QueryIntent:
    wants_formula: bool = False
    product_types: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QueryClassification:
    route: QueryRoute
    intent: QueryIntent
    query: str


def parse_query_intent(query: str) -> QueryIntent:
    q = query.strip()
    if not q:
        return QueryIntent()

    wants_formula = bool(
        re.search(
            r"\b(formula|formulation|ingredient|percentage|percentages|%|recipe|wtg)\b",
            q,
            re.I,
        )
        or _LOOKUP.search(q)
    )

    product_types: list[str] = []
    for tag, pattern in _QUERY_PRODUCT_MAP:
        if pattern.search(q):
            product_types.append(tag)

    keywords = [
        w.lower()
        for w in re.findall(r"[a-zA-Z]{4,}", q)
        if w.lower() not in {"give", "show", "formula", "with", "compare", "best"}
    ]

    return QueryIntent(
        wants_formula=wants_formula,
        product_types=product_types,
        keywords=keywords[:8],
    )


def classify_query(query: str) -> QueryClassification:
    q = query.strip()
    intent = parse_query_intent(q)

    if _ROLE_REASONING.search(q):
        return QueryClassification(route="reasoning", intent=intent, query=q)

    # Advice about suitability/usage must beat product-type lookup ("cream" ≠ recipe).
    if _ADVICE.search(q) and not _LOOKUP.search(q):
        return QueryClassification(route="reasoning", intent=intent, query=q)

    if _REASONING.search(q) and not _COMPARE.search(q):
        return QueryClassification(route="reasoning", intent=intent, query=q)

    if _COMPARE.search(q):
        intent.wants_formula = True
        return QueryClassification(route="compare", intent=intent, query=q)

    if _VAGUE_BEST.search(q):
        return QueryClassification(route="unknown", intent=intent, query=q)

    if intent.wants_formula or intent.product_types or _LOOKUP.search(q):
        return QueryClassification(route="lookup", intent=intent, query=q)

    if re.search(r"\b(why|how|explain)\b", q, re.I):
        return QueryClassification(route="reasoning", intent=intent, query=q)

    return QueryClassification(route="unknown", intent=intent, query=q)
