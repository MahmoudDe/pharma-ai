"""Embed a user query with BGE and run metadata-filtered Qdrant search with reranking."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from qdrant_client.http import models as qm

from app.config import get_settings
from app.ingestion.embed import embed_query
from app.ingestion.formula_detect import is_formula_chunk  # re-exported for callers
from app.ingestion.index import fetch_chunks_by_formulation_ids, get_client
from app.retrieval.intent import QueryIntent, parse_query_intent


logger = logging.getLogger(__name__)

_FORMULA_KEYWORDS = re.compile(
    r"\b(ingredient|ingredients|inqredient|raw materials|formula|formulation|procedure|parts|wt\.?|w/w)\b",
    re.IGNORECASE,
)
_NUMERIC_PERCENT = re.compile(r"\d[\d.,]*\s*%")
_WTG_PATTERN = re.compile(r"\bwtg\b", re.IGNORECASE)

_ANCHOR_MUST_TYPES = frozenset({"anti_dandruff"})
_RELAX_FORMULA_FILTER_TYPES = frozenset({"anti_dandruff"})

_TEXT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anti_dandruff", re.compile(r"\banti[-\s]?dandruff\b|\bantidandruff\b", re.I)),
    ("baby", re.compile(r"\bbaby\b", re.I)),
    ("shampoo", re.compile(r"\bshampoo\b", re.I)),
    ("hand_cream", re.compile(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", re.I)),
    ("cream", re.compile(r"\bcream\b", re.I)),
    ("lotion", re.compile(r"\blotion\b", re.I)),
]


@dataclass(slots=True)
class RetrievedChunk:
    doc_id: str
    doc_title: str
    pdf_page: int
    printed_page: int | None
    chunk_index: int
    text: str
    score: float
    chunk_type: str = "prose"
    section_title: str | None = None
    product_types: list[str] | None = None
    text_hash: str = ""
    formulation_id: str | None = None
    ingredient_count: int = 0
    extraction_confidence: float = 0.0

    @property
    def page(self) -> int:
        return self.printed_page if self.printed_page is not None else self.pdf_page

    def combined_text(self) -> str:
        parts = [self.section_title or "", self.text]
        return "\n".join(p for p in parts if p)


def _formula_boost_score(text: str) -> float:
    score = 0.0
    if is_formula_chunk(text):
        score += 0.20
    elif "%" in text or _NUMERIC_PERCENT.search(text):
        score += 0.08
    if _FORMULA_KEYWORDS.search(text):
        score += 0.06
    if "|" in text:
        score += 0.04
    if _WTG_PATTERN.search(text):
        score += 0.06
    return score


def _product_type_boost(chunk_products: list[str], intent: QueryIntent) -> float:
    if not intent.product_types or not chunk_products:
        return 0.0
    required = set(intent.product_types)
    chunk_set = set(chunk_products)
    overlap = required & chunk_set
    boost = 0.18 * len(overlap)
    missing = required - chunk_set
    boost -= 0.22 * len(missing)
    if required == {"baby", "shampoo"} and "baby" in chunk_set and "shampoo" not in chunk_set:
        boost -= 0.15
    if "anti_dandruff" in required and "anti_dandruff" not in chunk_set:
        boost -= 0.12
    return boost


def _text_intent_boost(chunk: RetrievedChunk, intent: QueryIntent, query: str) -> float:
    """Boost when section/body text matches query concepts (works even if payload tags are stale)."""
    combined = chunk.combined_text().lower()
    query_lower = query.lower()
    boost = 0.0

    for tag, pattern in _TEXT_PATTERNS:
        if tag not in intent.product_types and tag.replace("_", " ") not in query_lower:
            continue
        if pattern.search(combined):
            boost += 0.20 if is_formula_chunk(chunk.text) else 0.08
        elif tag in intent.product_types:
            boost -= 0.12

    if "anti_dandruff" in intent.product_types:
        if re.search(r"\banti[-\s]?dandruff\b|\bantidandruff\b", combined, re.I):
            boost += 0.25
        elif is_formula_chunk(chunk.text) and "shampoo" in combined and "dandruff" not in combined:
            boost -= 0.20

    if "baby" in intent.product_types and "shampoo" in intent.product_types:
        if re.search(r"\bbaby\s+shampoo\b", combined, re.I):
            boost += 0.22
        elif re.search(r"\bbaby\s+bath\b", combined, re.I) and "shampoo" not in combined:
            boost -= 0.18

    if re.search(r"\bhand\s+cream\b", query_lower, re.I):
        if re.search(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", combined, re.I):
            boost += 0.22
        elif "lotion" in combined and "cream" not in combined:
            boost -= 0.08

    return boost


def _query_phrase_boost(text: str, query: str) -> float:
    boost = 0.0
    text_lower = text.lower()
    query_lower = query.lower()
    is_formula = is_formula_chunk(text)

    phrases: list[tuple[str, str, float]] = [
        ("anti-dandruff", r"anti[-\s]?dandruff|antidandruff", 0.28),
        ("antidandruff", r"anti[-\s]?dandruff|antidandruff", 0.28),
        ("baby shampoo", r"baby\s+shampoo", 0.22),
        ("hand cream", r"hand\s+(and\s+)?(nail\s+)?cream", 0.22),
    ]
    for needle, pattern, amount in phrases:
        if needle in query_lower and re.search(pattern, text_lower):
            if is_formula:
                boost += amount
            elif re.search(r"\bstarting\s+(formula|formulation)\b", text_lower):
                boost -= 0.12
            else:
                boost += amount * 0.35
            break

    if re.search(r"\b(percentage|percentages)\b", query_lower) and is_formula:
        boost += 0.08

    return boost


def _build_filter(intent: QueryIntent, *, formula_only: bool = False) -> qm.Filter | None:
    must: list[qm.FieldCondition] = []
    should: list[qm.FieldCondition] = []

    relax_formula = bool(_RELAX_FORMULA_FILTER_TYPES & set(intent.product_types))
    if (formula_only or intent.wants_formula) and not relax_formula:
        must.append(
            qm.FieldCondition(key="is_formula", match=qm.MatchValue(value=True))
        )

    for pt in intent.product_types:
        if pt in _ANCHOR_MUST_TYPES:
            must.append(
                qm.FieldCondition(key="product_types", match=qm.MatchValue(value=pt))
            )
        else:
            should.append(
                qm.FieldCondition(key="product_types", match=qm.MatchValue(value=pt))
            )

    if not must and not should:
        return None
    return qm.Filter(must=must or None, should=should or None)


def _dedup_hits(hits: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: dict[tuple, RetrievedChunk] = {}
    for hit in hits:
        if hit.formulation_id:
            key = ("formulation_id", hit.formulation_id)
        else:
            key = (hit.doc_id, hit.pdf_page, hit.text_hash or hit.text[:200])
        existing = seen.get(key)
        if existing is None or hit.score > existing.score:
            seen[key] = hit
    return list(seen.values())


def _heuristic_bonus(h: RetrievedChunk, query: str, intent: QueryIntent) -> float:
    """Lightweight metadata boosts (cross-encoder carries most ranking signal)."""
    products = h.product_types or []
    bonus = (
        _formula_boost_score(h.text) * 0.5
        + _query_phrase_boost(h.text, query) * 0.4
        + _product_type_boost(products, intent) * 0.35
        + _text_intent_boost(h, intent, query) * 0.35
    )
    if h.formulation_id:
        bonus += 0.06
        if h.ingredient_count >= 6:
            bonus += 0.04
        elif h.ingredient_count >= 4:
            bonus += 0.02
        bonus += min(h.extraction_confidence, 0.9) * 0.03
    return bonus


def _rerank(hits: list[RetrievedChunk], query: str, intent: QueryIntent) -> list[RetrievedChunk]:
    wants_formula = intent.wants_formula or bool(
        re.search(r"\b(formula|formulation|ingredient|percentage|%|shampoo|cream|lotion)\b", query, re.I)
    )
    if not wants_formula or not hits:
        return hits

    settings = get_settings()
    pool = hits[: settings.rerank_top_n]

    if settings.enable_cross_encoder_rerank and len(pool) >= 2:
        from app.retrieval.rerank import cross_encoder_scores

        passages = [h.combined_text() for h in pool]
        ce_scores = cross_encoder_scores(query, passages)
        w_ce = settings.rerank_ce_weight
        w_vec = settings.rerank_vector_weight
        w_heu = settings.rerank_heuristic_weight
        for h, ce in zip(pool, ce_scores):
            heu = _heuristic_bonus(h, query, intent)
            h.score = w_ce * ce + w_vec * h.score + w_heu * min(heu, 1.0)
        pool = sorted(pool, key=lambda x: x.score, reverse=True)
        tail = hits[settings.rerank_top_n :]
        return pool + tail

    def key(h: RetrievedChunk) -> float:
        return h.score + _heuristic_bonus(h, query, intent)

    return sorted(hits, key=key, reverse=True)


def _chunk_from_payload(payload: dict, score: float) -> RetrievedChunk:
    pdf_page = int(payload.get("pdf_page") or payload.get("page") or 0)
    printed_raw = payload.get("printed_page")
    printed_page = int(printed_raw) if printed_raw is not None else None
    products = payload.get("product_types")
    product_list = [str(p) for p in products] if isinstance(products, list) else []
    return RetrievedChunk(
        doc_id=str(payload.get("doc_id", "")),
        doc_title=str(payload.get("doc_title", "")),
        pdf_page=pdf_page,
        printed_page=printed_page,
        chunk_index=int(payload.get("chunk_index", 0) or 0),
        text=str(payload.get("text", "")),
        score=score,
        chunk_type=str(payload.get("chunk_type", "formula")),
        section_title=payload.get("formula_name") or payload.get("section_title"),
        product_types=product_list,
        text_hash=str(payload.get("text_hash", "")),
        formulation_id=payload.get("formulation_id"),
        ingredient_count=int(payload.get("ingredient_count") or 0),
        extraction_confidence=float(payload.get("extraction_confidence") or 0.0),
    )


def _inject_structured_formula_chunks(
    results: list[RetrievedChunk],
    query: str,
    intent: QueryIntent,
) -> list[RetrievedChunk]:
    """Pin SQLite-best formulas into the vector candidate pool by formulation_id."""
    if not intent.wants_formula and not intent.product_types:
        return results

    from app.formulation.search import structured_search

    struct = structured_search(query, intent, limit=5)
    if not struct.matches:
        return results

    seen_fids = {r.formulation_id for r in results if r.formulation_id}
    ids_to_fetch: list[str] = []
    for i, ranked in enumerate(struct.matches[:3]):
        if ranked.score < 50:
            continue
        fid = ranked.record.id
        if fid and fid not in seen_fids:
            ids_to_fetch.append(fid)
            seen_fids.add(fid)

    if not ids_to_fetch:
        return results

    payloads = fetch_chunks_by_formulation_ids(ids_to_fetch)
    injected: list[RetrievedChunk] = []
    for i, payload in enumerate(payloads):
        if not payload or not payload.get("formulation_id"):
            continue
        injected.append(_chunk_from_payload(payload, score=0.92 - i * 0.02))

    return injected + results


def _hit_to_chunk(hit, score: float) -> RetrievedChunk:
    payload = hit.payload or {}
    pdf_page = int(payload.get("pdf_page") or payload.get("page") or 0)
    printed_raw = payload.get("printed_page")
    printed_page = int(printed_raw) if printed_raw is not None else None
    products = payload.get("product_types")
    if isinstance(products, list):
        product_list = [str(p) for p in products]
    else:
        product_list = []
    return RetrievedChunk(
        doc_id=str(payload.get("doc_id", "")),
        doc_title=str(payload.get("doc_title", "")),
        pdf_page=pdf_page,
        printed_page=printed_page,
        chunk_index=int(payload.get("chunk_index", 0) or 0),
        text=str(payload.get("text", "")),
        score=score,
        chunk_type=str(payload.get("chunk_type", "prose")),
        section_title=payload.get("section_title"),
        product_types=product_list,
        text_hash=str(payload.get("text_hash", "")),
        formulation_id=payload.get("formulation_id"),
        ingredient_count=int(payload.get("ingredient_count") or 0),
        extraction_confidence=float(payload.get("extraction_confidence") or 0.0),
    )


def search(
    query: str,
    *,
    top_k: int = 10,
    fetch_k: int | None = None,
    formula_only: bool = False,
    product_type: str | None = None,
) -> list[RetrievedChunk]:
    if not query or not query.strip():
        return []

    intent = parse_query_intent(query)
    if product_type:
        if product_type not in intent.product_types:
            intent.product_types.append(product_type)

    settings = get_settings()
    client = get_client()
    vector = embed_query(query)

    effective_fetch = fetch_k or (50 if (intent.wants_formula or formula_only or intent.product_types) else 30)
    qfilter = _build_filter(intent, formula_only=formula_only)

    hits = client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector.tolist(),
        query_filter=qfilter,
        limit=effective_fetch,
        with_payload=True,
    ).points

    results = [_hit_to_chunk(hit, float(hit.score or 0.0)) for hit in hits]

    if "anti_dandruff" in intent.product_types:
        anchor_filter = qm.Filter(
            must=[
                qm.FieldCondition(
                    key="product_types", match=qm.MatchValue(value="anti_dandruff")
                )
            ]
        )
        anchor_hits = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector.tolist(),
            query_filter=anchor_filter,
            limit=min(effective_fetch, 40),
            with_payload=True,
        ).points
        seen_ids = {f"{r.doc_id}:{r.pdf_page}:{r.chunk_index}" for r in results}
        for hit in anchor_hits:
            key = f"{hit.payload.get('doc_id')}:{hit.payload.get('pdf_page')}:{hit.payload.get('chunk_index')}"
            if key not in seen_ids:
                results.append(_hit_to_chunk(hit, float(hit.score or 0.0)))
                seen_ids.add(key)

    results = _inject_structured_formula_chunks(results, query, intent)
    results = _dedup_hits(results)
    results = _rerank(results, query, intent)
    results = results[:top_k]

    logger.info(
        "Retrieved %d chunks for query (top score=%.3f, filter=%s)",
        len(results),
        results[0].score if results else 0.0,
        bool(qfilter),
    )
    return results
