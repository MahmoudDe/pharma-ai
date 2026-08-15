from __future__ import annotations

import re
from functools import lru_cache

from app.config import get_settings
from app.formulation.schemas import FormulationRecord
from app.formulation.store_base import FormulationSearchFilters, FormulationStore
from app.formulation.store_sqlite import DB_PATH, SQLiteFormulationStore, new_formulation_id
from app.retrieval.intent import QueryIntent

__all__ = [
    "DB_PATH",
    "FormulationSearchFilters",
    "FormulationStore",
    "clear_all_formulations",
    "get_formulation",
    "get_store",
    "init_db",
    "list_formulations",
    "new_formulation_id",
    "search_by_intent",
    "upsert_formulation",
]


@lru_cache
def get_store() -> FormulationStore:
    settings = get_settings()
    if settings.formulation_store == "postgres":
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required when FORMULATION_STORE=postgres")
        from app.formulation.store_postgres import PostgresFormulationStore

        return PostgresFormulationStore(settings.database_url)
    return SQLiteFormulationStore()


def init_db() -> None:
    get_store().init_db()


def upsert_formulation(record: FormulationRecord) -> None:
    get_store().upsert(record)


def get_formulation(formulation_id: str) -> FormulationRecord | None:
    return get_store().get(formulation_id)


def clear_all_formulations() -> int:
    return get_store().clear_all()


def list_formulations(
    *,
    product_types: list[str] | None = None,
    product_type: str | None = None,
    ingredient: str | None = None,
    name_contains: str | None = None,
    doc_id: str | None = None,
    banned_ingredients: list[str] | None = None,
    preferred_ingredients: list[str] | None = None,
    limit: int = 20,
) -> list[FormulationRecord]:
    filters = FormulationSearchFilters(
        product_types=product_types,
        product_type=product_type,
        ingredient=ingredient,
        name_contains=name_contains,
        doc_id=doc_id,
        banned_ingredients=banned_ingredients,
        preferred_ingredients=preferred_ingredients,
        limit=limit,
    )
    return get_store().search(filters)


def count_formulations() -> int:
    return get_store().count()


def _name_relevance_score(name: str, intent: QueryIntent, query: str) -> float:
    name_lower = name.lower()
    query_lower = query.lower()
    score = 0.0
    if "baby" in intent.product_types and "shampoo" in intent.product_types:
        if "baby" in name_lower and "shampoo" in name_lower:
            score += 3.0
        elif "baby" in name_lower and "bath" in name_lower:
            score -= 2.0
    if "anti_dandruff" in intent.product_types:
        if "anti" in name_lower and "dandruff" in name_lower:
            score += 3.0
        elif "antidandruff" in name_lower.replace(" ", ""):
            score += 3.0
        if "shampoo" in intent.product_types:
            compact = name_lower.replace(" ", "").replace("-", "")
            if "shampoo" in name_lower or "shamdoo" in compact or "shamwoo" in compact:
                score += 3.0
            elif "cream" in name_lower:
                score -= 2.5
            elif "lotion" in name_lower:
                score -= 2.0
    if re.search(r"\bhand\s+cream\b", query_lower, re.I):
        if re.search(r"\btube[-\s]?dispensed\b", name_lower, re.I):
            score += 4.0
        elif re.search(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", name_lower, re.I):
            score += 2.5
    for kw in intent.keywords:
        if len(kw) >= 4 and kw in name_lower:
            score += 0.5
    return score


def _structured_product_filter(intent: QueryIntent) -> list[str] | None:
    types = list(intent.product_types)
    if "anti_dandruff" in types and "shampoo" in types:
        return ["anti_dandruff"]
    if "baby" in types and "shampoo" in types:
        return ["baby", "shampoo"]
    return types or None


def search_by_intent(intent: QueryIntent, query: str = "", limit: int = 3) -> list[FormulationRecord]:
    if not intent.wants_formula and not intent.product_types:
        return []

    filter_types = _structured_product_filter(intent)
    records = list_formulations(
        product_types=filter_types,
        ingredient=None,
        limit=limit * 8,
    )

    if not records and intent.product_types:
        for pt in intent.product_types:
            records.extend(list_formulations(product_type=pt, limit=limit * 4))

    query_lower = query.lower()
    scored: list[tuple[float, FormulationRecord]] = []
    for rec in records:
        if len(rec.ingredients) < 2:
            continue
        relevance = _name_relevance_score(rec.name, intent, query)
        ing_bonus = min(len(rec.ingredients), 24) * 0.06
        if re.search(r"\bhand\s+cream\b", query_lower, re.I) and re.search(
            r"\btube[-\s]?dispensed\b", rec.name, re.I
        ):
            relevance += 5.0
        scored.append((rec.confidence + relevance * 0.2 + ing_bonus, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_by_name: dict[str, FormulationRecord] = {}
    for _, rec in scored:
        key = rec.name.lower()[:80]
        prev = best_by_name.get(key)
        if prev is None or len(rec.ingredients) > len(prev.ingredients):
            best_by_name[key] = rec

    out = sorted(
        best_by_name.values(),
        key=lambda r: next(s for s, rec in scored if rec.id == r.id),
        reverse=True,
    )
    score_map = {rec.id: sc for sc, rec in scored}
    out.sort(key=lambda r: score_map.get(r.id, 0.0), reverse=True)
    return out[:limit]
