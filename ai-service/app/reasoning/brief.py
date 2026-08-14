"""Apply optional structured_brief constraints to intent and formulation results."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.regulatory import check_formulation
from app.formulation.schemas import FormulationRecord
from app.formulation.cost import estimate_formulation_cost
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


def brief_markets(brief: StructuredBrief | None) -> list[str]:
    if brief is None or not brief.markets:
        return []
    return [m.strip().upper() for m in brief.markets if m and m.strip()]


def formulation_compliance_status(record: FormulationRecord, markets: list[str]) -> str:
    if not markets:
        return "pass"
    return check_formulation(record, markets).status


def formulation_cost_per_kg(record: FormulationRecord) -> float | None:
    return estimate_formulation_cost(record).cost_per_kg


def cost_target_score(record: FormulationRecord, brief: StructuredBrief | None) -> float:
    if brief is None or brief.cost_target is None:
        return 0.0
    cost = formulation_cost_per_kg(record)
    target = float(brief.cost_target)
    if cost is None:
        return -6.0
    if cost <= target:
        return min(12.0, 6.0 + (target - cost) / max(target, 0.01) * 4.0)
    excess = (cost - target) / max(target, 0.01)
    return -min(30.0, 8.0 + excess * 20.0)


def exceeds_cost_target(record: FormulationRecord, brief: StructuredBrief | None) -> bool:
    if brief is None or brief.cost_target is None:
        return False
    cost = formulation_cost_per_kg(record)
    if cost is None:
        return False
    return cost > float(brief.cost_target) * 1.1


def apply_brief_filters(
    records: list[FormulationRecord],
    brief: StructuredBrief | None,
) -> list[FormulationRecord]:
    if brief is None:
        return records
    out = records
    banned = normalize_brief_terms(brief.banned_ingredients)
    if banned:
        out = [r for r in out if not formulation_has_banned(r, banned)]
    markets = brief_markets(brief)
    if markets:
        out = [r for r in out if formulation_compliance_status(r, markets) != "fail"]
    if brief.cost_target is not None:
        out = [r for r in out if not exceeds_cost_target(r, brief)]
    return out
