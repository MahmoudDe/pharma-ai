"""Ingredient substitution suggestions."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import FormulationRecord
from app.formulation.store import list_formulations
from app.schemas import CitedEvidence, StructuredBrief


logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "substitutions.json"


@dataclass(slots=True)
class SubstitutionSuggestion:
    substitute: str
    confidence: float
    reason: str
    source: str
    citations: list[CitedEvidence] = field(default_factory=list)


def _load_rules() -> list[dict]:
    if not _DATA_PATH.is_file():
        return []
    try:
        return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid substitutions.json")
        return []


def _matches_ingredient(target: str, rule_from: str, aliases: list[str]) -> bool:
    t = target.lower()
    candidates = [rule_from.lower(), *[a.lower() for a in aliases]]
    return any(c in t or t in c for c in candidates if c)


def _rule_suggestions(
    record: FormulationRecord,
    ingredient_query: str,
    brief: StructuredBrief | None,
) -> list[SubstitutionSuggestion]:
    banned = []
    if brief and brief.banned_ingredients:
        banned = [normalize_ingredient_name(x) or x.lower() for x in brief.banned_ingredients]

    out: list[SubstitutionSuggestion] = []
    for rule in _load_rules():
        if not _matches_ingredient(
            ingredient_query,
            rule.get("from", ""),
            rule.get("aliases_from", []),
        ):
            continue
        substitute = rule.get("to", "")
        sub_norm = normalize_ingredient_name(substitute) or substitute.lower()
        if any(b and (b in sub_norm or sub_norm in b) for b in banned):
            continue
        product_types = rule.get("product_types") or []
        if product_types and not any(pt in record.product_types for pt in product_types):
            continue
        out.append(
            SubstitutionSuggestion(
                substitute=substitute,
                confidence=float(rule.get("confidence", 0.7)),
                reason=rule.get("reason", "Curated substitution rule"),
                source="rule_table",
            )
        )
    return out


def _corpus_suggestions(
    record: FormulationRecord,
    ingredient_query: str,
) -> list[SubstitutionSuggestion]:
    norm = normalize_ingredient_name(ingredient_query) or ingredient_query.lower()
    product_types = record.product_types or None
    peers = list_formulations(
        product_types=product_types,
        limit=40,
    )
    counts: dict[str, int] = {}
    for peer in peers:
        if peer.id == record.id:
            continue
        has_source = any(
            (ing.normalized_name or "").lower().find(norm) >= 0
            or norm in (ing.raw_name or "").lower()
            for ing in record.ingredients
        )
        if not has_source:
            continue
        for ing in peer.ingredients:
            name = ing.normalized_name or normalize_ingredient_name(ing.raw_name) or ing.raw_name
            key = name.lower()
            if norm in key or key in norm:
                continue
            counts[key] = counts.get(key, 0) + 1

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    out: list[SubstitutionSuggestion] = []
    for name, freq in ranked:
        out.append(
            SubstitutionSuggestion(
                substitute=name,
                confidence=min(0.9, 0.5 + freq * 0.08),
                reason=f"Appears in {freq} similar corpus formula(s) without {ingredient_query}.",
                source="corpus_cooccurrence",
                citations=[
                    CitedEvidence(
                        document_id=record.doc_id,
                        pdf_page=record.pdf_page,
                        quote=f"Corpus peer ingredient: {name}",
                    )
                ],
            )
        )
    return out


def suggest_substitutions(
    record: FormulationRecord,
    ingredient: str,
    *,
    brief: StructuredBrief | None = None,
    limit: int = 5,
) -> list[SubstitutionSuggestion]:
    if not ingredient.strip():
        return []

    merged: dict[str, SubstitutionSuggestion] = {}
    for sug in _rule_suggestions(record, ingredient, brief):
        merged[sug.substitute.lower()] = sug
    for sug in _corpus_suggestions(record, ingredient):
        key = sug.substitute.lower()
        if key not in merged or sug.confidence > merged[key].confidence:
            merged[key] = sug

    ranked = sorted(merged.values(), key=lambda s: s.confidence, reverse=True)
    return ranked[:limit]
