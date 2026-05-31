"""Apply optional structured_brief constraints to intent and formulation results."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import FormulationRecord
from app.retrieval.intent import QueryIntent
from app.schemas import StructuredBrief


def merge_intent_with_brief(intent: QueryIntent, brief: StructuredBrief | None) -> QueryIntent:
    if brief is None:
        return intent
    types = list(intent.product_types)
    if brief.product_type:
        pt = brief.product_type.strip().lower().replace(" ", "_")
        if pt and pt not in types:
            types.append(pt)
    keywords = list(intent.keywords)
    for attr in brief.target_attributes or []:
        token = attr.strip().lower()
        if len(token) >= 3 and token not in keywords:
            keywords.append(token)
    return QueryIntent(
        wants_formula=intent.wants_formula or bool(brief.product_type),
        product_types=types,
        keywords=keywords[:12],
    )


def normalize_brief_terms(terms: list[str] | None) -> list[str]:
    if not terms:
        return []
    out: list[str] = []
    for term in terms:
        for part in re.split(r"[,;]+", term):
            n = normalize_ingredient_name(part.strip())
            if n and n not in out:
                out.append(n)
    return out


def formulation_has_banned(record: FormulationRecord, banned: list[str]) -> bool:
    if not banned:
        return False
    for ing in record.ingredients:
        raw = (ing.raw_name or "").lower()
        norm = (ing.normalized_name or normalize_ingredient_name(ing.raw_name) or "").lower()
        for b in banned:
            if b in raw or b in norm or raw in b or norm in b:
                return True
    return False


def preferred_ingredient_score(record: FormulationRecord, preferred: list[str]) -> float:
    if not preferred:
        return 0.0
    score = 0.0
    for ing in record.ingredients:
        raw = (ing.raw_name or "").lower()
        norm = (ing.normalized_name or normalize_ingredient_name(ing.raw_name) or "").lower()
        for p in preferred:
            if p in raw or p in norm or raw in p or norm in p:
                score += 8.0
                break
    return min(score, 24.0)


def apply_brief_filters(
    records: list[FormulationRecord],
    brief: StructuredBrief | None,
) -> list[FormulationRecord]:
    if brief is None:
        return records
    banned = normalize_brief_terms(brief.banned_ingredients)
    if not banned:
        return records
    return [r for r in records if not formulation_has_banned(r, banned)]
