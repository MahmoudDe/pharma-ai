"""Confidence-scored structured formulation search."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.formulation.schemas import FormulationRecord
from app.formulation.store import list_formulations
from app.reasoning.brief import (
    brief_markets,
    formulation_compliance_status,
    merge_intent_with_brief,
    normalize_brief_terms,
    preferred_ingredient_score,
)
from app.retrieval.intent import QueryIntent, parse_query_intent
from app.retrieval.query_signals import (
    QuerySignals,
    extract_query_signals,
    fuzzy_name_match,
    record_has_ingredient,
)
from app.schemas import StructuredBrief

RouteHint = Literal["direct", "hybrid", "fallback"]

TRUSTED_DOC_PREFIXES = (
    "cosmetic_and_toiletry",
    "formulas_ingredients",
    "production_of_cosmetics",
)

_MODIFIER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anti_dandruff", re.compile(r"\banti[-\s]?dandruff\b|\bantidandruff\b", re.I)),
    ("baby", re.compile(r"\bbaby\b", re.I)),
    ("sulfate_free", re.compile(r"\bsulfate[-\s]?free\b", re.I)),
    ("hand_cream", re.compile(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", re.I)),
]


@dataclass(slots=True)
class RankedFormulation:
    record: FormulationRecord
    score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class StructuredSearchResult:
    matches: list[RankedFormulation]
    top_confidence: float
    route_hint: RouteHint


def _record_has_product_types(record: FormulationRecord, required: list[str]) -> bool:
    tags = set(record.product_types)
    combined = f"{record.name}\n{record.source_text}".lower()
    for t in required:
        if t in tags:
            continue
        if t == "anti_dandruff" and re.search(r"anti[-\s]?dandruff|antidandruff", combined, re.I):
            continue
        if t == "baby" and "baby" in combined:
            continue
        if t == "shampoo" and ("shampoo" in combined or "shamdoo" in combined.replace(" ", "")):
            continue
        if t == "cream" and "cream" in combined:
            continue
        return False
    return True


def _modifier_score(query: str, record: FormulationRecord) -> float:
    combined = f"{record.name} {query}".lower()
    score = 0.0
    for _name, pattern in _MODIFIER_PATTERNS:
        if pattern.search(query) and pattern.search(combined):
            score = 30.0
            break
    return score


def _name_bonus(record: FormulationRecord, intent: QueryIntent, query: str) -> float:
    name_lower = record.name.lower()
    query_lower = query.lower()
    bonus = 0.0
    if "baby" in intent.product_types and "baby" in name_lower and "shampoo" in name_lower:
        bonus += 10.0
    if "anti_dandruff" in intent.product_types:
        if "dandruff" in name_lower.replace("-", ""):
            bonus += 10.0
        compact = name_lower.replace(" ", "").replace("-", "")
        if "shampoo" in intent.product_types:
            if "shamdoo" in compact or "shampoo" in name_lower:
                bonus += 12.0
            elif "lotion" in name_lower and "shampoo" not in name_lower:
                bonus -= 10.0
    if re.search(r"\bhand\s+cream\b", query_lower, re.I):
        if re.search(r"\btube[-\s]?dispensed\b", name_lower, re.I):
            bonus += 18.0
        elif re.search(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", name_lower, re.I):
            bonus += 8.0
        elif "baby" in name_lower:
            bonus -= 15.0
        elif "shampoo" in name_lower:
            bonus -= 10.0
    return bonus


def _query_hand_cream(query: str) -> bool:
    return bool(re.search(r"\bhand\s+cream\b", query, re.I))


def _ingredient_match_score(record: FormulationRecord, signals: QuerySignals) -> float:
    if not signals.required_ingredients:
        return 0.0
    hits = sum(1 for ing in signals.required_ingredients if record_has_ingredient(record, ing))
    total = len(signals.required_ingredients)
    if hits == total:
        return 35.0
    if hits > 0:
        return 8.0 * hits - 15.0
    return -25.0


def _named_formula_score(record: FormulationRecord, signals: QuerySignals) -> float:
    if not signals.named_formulas:
        return 0.0
    best = 0.0
    combined = f"{record.name}\n{record.source_text[:400]}"
    for name in signals.named_formulas:
        if fuzzy_name_match(name, record.name):
            best = max(best, 30.0)
        elif fuzzy_name_match(name, combined):
            best = max(best, 18.0)
        elif best <= 0:
            best = -12.0
    return best


def score_formulation(
    record: FormulationRecord,
    intent: QueryIntent,
    query: str,
    *,
    brief: StructuredBrief | None = None,
    signals: QuerySignals | None = None,
) -> RankedFormulation:
    signals = signals or extract_query_signals(query)
    breakdown: dict[str, float] = {}
    required = intent.product_types

    if required and _record_has_product_types(record, required):
        breakdown["product_type_match"] = 40.0
    elif required:
        breakdown["product_type_match"] = 0.0
    else:
        breakdown["product_type_match"] = 20.0

    mod = _modifier_score(query, record)
    breakdown["modifier_match"] = mod

    ing_count = len(record.ingredients)
    breakdown["ingredient_completeness"] = min(ing_count, 15) / 15.0 * 20.0

    if any(record.doc_id.startswith(p) for p in TRUSTED_DOC_PREFIXES):
        breakdown["source_quality"] = 10.0
    else:
        breakdown["source_quality"] = 5.0

    breakdown["name_bonus"] = _name_bonus(record, intent, query)
    if brief:
        preferred = normalize_brief_terms(brief.preferred_ingredients)
        breakdown["preferred_ingredients"] = preferred_ingredient_score(record, preferred)
        markets = brief_markets(brief)
        if markets:
            compliance = formulation_compliance_status(record, markets)
            if compliance == "fail":
                breakdown["compliance"] = -100.0
            elif compliance == "warn":
                breakdown["compliance"] = -12.0
            else:
                breakdown["compliance"] = 4.0

    breakdown["ingredient_match"] = _ingredient_match_score(record, signals)
    breakdown["named_formula"] = _named_formula_score(record, signals)

    if _query_hand_cream(query):
        name_lower = record.name.lower()
        if re.search(r"\btube[-\s]?dispensed\b", name_lower, re.I):
            breakdown["hand_cream_title"] = 25.0
        elif re.search(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", name_lower, re.I):
            breakdown["hand_cream_title"] = 10.0
        elif "baby" in name_lower or "shampoo" in name_lower:
            breakdown["hand_cream_title"] = -20.0

    total = min(100.0, max(0.0, sum(breakdown.values())))
    return RankedFormulation(record=record, score=total, score_breakdown=breakdown)


def _best_for_target(
    target: str,
    ranked: list[RankedFormulation],
) -> RankedFormulation | None:
    for r in ranked:
        if fuzzy_name_match(target, r.record.name):
            return r
    target_signals = extract_query_signals(target)
    for r in ranked:
        if _named_formula_score(r.record, target_signals) >= 18.0:
            return r
    return ranked[0] if ranked else None


def structured_search_for_compare(
    query: str,
    intent: QueryIntent,
    signals: QuerySignals,
    *,
    limit: int = 5,
    brief: StructuredBrief | None = None,
) -> list[FormulationRecord]:
    """Find one best match per named compare target."""
    targets = signals.compare_targets or signals.named_formulas
    if len(targets) < 2:
        return []

    found: list[FormulationRecord] = []
    seen_ids: set[str] = set()
    for target in targets[:3]:
        sub_intent = parse_query_intent(target)
        sub_result = structured_search(target, sub_intent, limit=limit, brief=brief)
        pick = _best_for_target(target, sub_result.matches)
        if pick and pick.record.id not in seen_ids:
            seen_ids.add(pick.record.id)
            found.append(pick.record)
    return found


def _filter_types_for_intent(intent: QueryIntent) -> list[str] | None:
    types = list(intent.product_types)
    if "anti_dandruff" in types and "shampoo" in types:
        return ["anti_dandruff"]
    return types or None


def structured_search(
    query: str,
    intent: QueryIntent,
    *,
    limit: int = 5,
    brief: StructuredBrief | None = None,
) -> StructuredSearchResult:
    intent = merge_intent_with_brief(intent, brief)
    signals = extract_query_signals(query)
    filter_types = _filter_types_for_intent(intent)
    banned = normalize_brief_terms(brief.banned_ingredients) if brief else None
    candidates = list_formulations(
        product_types=filter_types,
        banned_ingredients=banned,
        limit=limit * 12,
    )

    if not candidates and intent.product_types:
        for pt in intent.product_types:
            candidates.extend(
                list_formulations(
                    product_type=pt,
                    banned_ingredients=banned,
                    limit=limit * 6,
                )
            )

    if signals.required_ingredients and len(candidates) < limit * 4:
        for ing in signals.required_ingredients[:3]:
            candidates.extend(
                list_formulations(
                    ingredient=ing.split()[0] if ing else None,
                    banned_ingredients=banned,
                    limit=limit * 4,
                )
            )

    ranked: list[RankedFormulation] = []
    seen_names: dict[str, RankedFormulation] = {}
    for rec in candidates:
        if len(rec.ingredients) < 2:
            continue
        r = score_formulation(rec, intent, query, brief=brief, signals=signals)
        key = rec.name.lower()[:80]
        prev = seen_names.get(key)
        if prev is None or len(rec.ingredients) > len(prev.record.ingredients):
            seen_names[key] = r

    ranked = sorted(seen_names.values(), key=lambda x: x.score, reverse=True)

    markets = brief_markets(brief)
    if markets:
        ranked = [
            r for r in ranked if formulation_compliance_status(r.record, markets) != "fail"
        ]

    if _query_hand_cream(query):
        def _hand_cream_rank(r: RankedFormulation) -> tuple[int, float]:
            name = r.record.name.lower()
            if re.search(r"\btube[-\s]?dispensed\b", name, re.I):
                tier = 0
            elif re.search(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", name, re.I):
                tier = 1
            else:
                tier = 2
            return (tier, -r.score)

        ranked = sorted(ranked, key=_hand_cream_rank)

    if "anti_dandruff" in intent.product_types and "shampoo" in intent.product_types:
        ranked = sorted(
            ranked,
            key=lambda r: (
                0
                if re.search(r"sham|shampoo", r.record.name.replace(" ", ""), re.I)
                else 1,
                -r.score,
            ),
        )

    ranked = ranked[:limit]

    from app.config import get_settings

    settings = get_settings()
    top = ranked[0].score if ranked else 0.0
    if top >= settings.structured_direct_threshold:
        hint: RouteHint = "direct"
    elif top >= settings.structured_hybrid_threshold:
        hint = "hybrid"
    else:
        hint = "fallback"

    return StructuredSearchResult(matches=ranked, top_confidence=top, route_hint=hint)
