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
from app.retrieval.query_signals import extract_query_signals, record_has_ingredient


logger = logging.getLogger(__name__)

_FORMULA_KEYWORDS = re.compile(
    r"\b(ingredient|ingredients|inqredient|raw materials|formula|formulation|procedure|parts|wt\.?|w/w)\b",
    re.IGNORECASE,
)
_NUMERIC_PERCENT = re.compile(r"\d[\d.,]*\s*%")
_WTG_PATTERN = re.compile(r"\bwtg\b", re.IGNORECASE)

_ANCHOR_MUST_TYPES = frozenset({"anti_dandruff", "makeup", "deodorant", "toner", "soap"})
_RELAX_FORMULA_FILTER_TYPES = frozenset({"anti_dandruff", "toner", "deodorant", "makeup"})

_TEXT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anti_dandruff", re.compile(r"\banti[-\s]?dandruff\b|\bantidandruff\b", re.I)),
    ("baby", re.compile(r"\bbaby\b", re.I)),
    ("shampoo", re.compile(r"\bshampoo\b|\bsham[d]?oo\b", re.I)),
    ("hand_cream", re.compile(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", re.I)),
    ("cream", re.compile(r"\bcream\b|\bgel\s+cream\b", re.I)),
    ("lotion", re.compile(r"\blotion\b", re.I)),
    ("sunscreen", re.compile(r"\bsunscreen\b|\bspf\b|\bsolar\s+protection\b|\bsuntan\b", re.I)),
    ("conditioner", re.compile(r"\bcondition(er|ing)\b|\bleave[-\s]?in\b", re.I)),
    ("soap", re.compile(r"\bsoap\b|\bhand\s+cleaner\b", re.I)),
    ("makeup", re.compile(r"\blipstick\b|\bmake[-\s]?up\b|\blip\s+balm\b", re.I)),
    ("deodorant", re.compile(r"\bdeodorant\b|\bantiperspirant\b", re.I)),
    ("cleanser", re.compile(r"\bcleanser\b|\bfacial\s+wash\b|\bcleansing\b", re.I)),
    ("toner", re.compile(r"\btoner\b", re.I)),
    ("gel", re.compile(r"\bgel\b|\bshower\s+(?:gel|bath)\b", re.I)),
]

# Query phrases → chunk text patterns. Rare types need strong exact-phrase boosts
# because many chunks were ingested without those product_types tags.
_PHRASE_BOOSTS: list[tuple[str, str, float]] = [
    ("anti-dandruff", r"anti[-\s]?dandruff|antidandruff", 0.28),
    ("antidandruff", r"anti[-\s]?dandruff|antidandruff", 0.28),
    ("baby shampoo", r"baby\s+shampoo", 0.22),
    ("hand cream", r"hand\s+(and\s+)?(nail\s+)?cream", 0.22),
    ("hand and nail", r"hand\s+and\s+nail", 0.24),
    ("lipstick", r"lipstick", 0.35),
    ("makeup", r"make[-\s]?up|lipstick", 0.28),
    ("deodorant", r"deodorant|antiperspirant", 0.32),
    ("antiperspirant", r"deodorant|antiperspirant", 0.32),
    ("toner", r"\btoner\b", 0.35),
    ("facial cleanser", r"facial\s+cleanser|cleanser|facial\s+wash", 0.28),
    ("cleanser", r"cleanser|facial\s+wash|cleansing", 0.24),
    ("shower gel", r"shower\s+(?:gel|bath)|\bgel\b", 0.26),
    ("shower bath", r"shower\s+(?:gel|bath)", 0.28),
    ("leave-in", r"leave[-\s]?in|conditioner", 0.24),
    ("conditioner", r"condition(er|ing)|leave[-\s]?in", 0.20),
    ("gel cream", r"gel\s+cream|\bgel\b", 0.24),
    ("shaving cream", r"shav(?:e|ing)\s+cream|\bshav", 0.28),
    ("body soap", r"\bsoap\b|hand\s+cleaner", 0.26),
    ("sunscreen", r"sunscreen|solar\s+protection|\bspf\b|suntan", 0.24),
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
    # Softer miss penalty — text match can recover rare types with stale tags.
    boost -= 0.10 * len(missing)
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
            boost += 0.22 if is_formula_chunk(chunk.text) else 0.10
        elif tag in intent.product_types:
            # Do not heavily punish missing tags when the type is rare / often untagged.
            if tag in {"makeup", "deodorant", "toner", "cleanser", "gel", "soap"}:
                boost -= 0.04
            else:
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

    # Keep lotion/cream queries from being flooded by shampoo chunks.
    skin_types = {"lotion", "cream", "moisturizer"} & set(intent.product_types)
    hair_types = {"shampoo", "conditioner", "anti_dandruff"} & set(intent.product_types)
    if skin_types and not hair_types:
        if re.search(r"\bshampoo\b|\bsham[d]?oo\b|\bcondition", combined, re.I):
            boost -= 0.28
        if re.search(r"\blotion\b|\bcream\b|\bemollient|\bmoistur", combined, re.I):
            boost += 0.12 if is_formula_chunk(chunk.text) else 0.05

    if "makeup" in intent.product_types and re.search(r"\blipstick\b|\bmake[-\s]?up\b", combined, re.I):
        boost += 0.30 if is_formula_chunk(chunk.text) else 0.18
    if "toner" in intent.product_types and re.search(r"\btoner\b", combined, re.I):
        boost += 0.32 if is_formula_chunk(chunk.text) else 0.18
    if "deodorant" in intent.product_types and re.search(
        r"\bdeodorant\b|\bantiperspirant\b", combined, re.I
    ):
        boost += 0.30 if is_formula_chunk(chunk.text) else 0.16

    return boost


def _query_phrase_boost(text: str, query: str) -> float:
    boost = 0.0
    text_lower = text.lower()
    query_lower = query.lower()
    is_formula = is_formula_chunk(text)

    for needle, pattern, amount in _PHRASE_BOOSTS:
        if needle in query_lower and re.search(pattern, text_lower):
            if is_formula:
                boost += amount
            elif re.search(r"\bstarting\s+(formula|formulation)\b", text_lower):
                boost -= 0.12
            else:
                boost += amount * 0.40
            break

    if re.search(r"\b(percentage|percentages)\b", query_lower) and is_formula:
        boost += 0.08

    signals = extract_query_signals(query)
    combined = text.lower()
    for ing in signals.required_ingredients:
        if ing.lower() in combined:
            boost += 0.22 if is_formula else 0.10
    for name in signals.named_formulas + signals.compare_targets:
        if name.lower()[:20] in combined or any(
            tok in combined for tok in name.lower().split() if len(tok) >= 5
        ):
            boost += 0.18 if is_formula else 0.08

    return boost


def _prefer_on_type_formulas(
    hits: list[RetrievedChunk],
    query: str,
    intent: QueryIntent,
) -> list[RetrievedChunk]:
    """When asking for formulas, surface on-type formula chunks ahead of off-type prose."""
    if not hits or not (intent.wants_formula or intent.product_types):
        return hits

    query_lower = query.lower()
    required = set(intent.product_types)

    def on_type(h: RetrievedChunk) -> bool:
        tags = set(h.product_types or [])
        combined = h.combined_text().lower()
        if required and tags & required:
            return True
        for tag, pattern in _TEXT_PATTERNS:
            if tag in required or tag.replace("_", " ") in query_lower:
                if pattern.search(combined):
                    return True
        for needle, pattern, _ in _PHRASE_BOOSTS:
            if needle in query_lower and re.search(pattern, combined):
                return True
        return False

    formulas_on = [h for h in hits if is_formula_chunk(h.text) and on_type(h)]
    formulas_other = [h for h in hits if is_formula_chunk(h.text) and not on_type(h)]
    rest = [h for h in hits if not is_formula_chunk(h.text)]

    # Compare / multi-formula: keep at least two formula chunks near the top when available.
    if re.search(r"\b(compare|comparison|difference|vs\.?)\b", query_lower, re.I):
        preferred = formulas_on[:4] + formulas_other[:2]
        preferred_ids = {id(h) for h in preferred}
        return preferred + [h for h in hits if id(h) not in preferred_ids]

    if formulas_on:
        preferred = formulas_on[:3]
        preferred_ids = {id(h) for h in preferred}
        return preferred + [h for h in hits if id(h) not in preferred_ids]

    return hits


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


def _chunk_fusion_key(chunk: RetrievedChunk) -> str:
    if chunk.formulation_id:
        return f"formula:{chunk.formulation_id}"
    return f"{chunk.doc_id}:{chunk.pdf_page}:{chunk.chunk_index}"


def _bm25_to_chunk(record, score: float) -> RetrievedChunk:
    products = record.product_types or []
    return RetrievedChunk(
        doc_id=record.doc_id,
        doc_title=record.doc_title,
        pdf_page=record.pdf_page,
        printed_page=record.printed_page,
        chunk_index=record.chunk_index,
        text=record.text,
        score=score,
        chunk_type=record.chunk_type,
        section_title=record.section_title,
        product_types=list(products),
        text_hash=record.text_hash,
        formulation_id=record.formulation_id,
        ingredient_count=record.ingredient_count,
        extraction_confidence=record.extraction_confidence,
    )


def _rrf_fuse(
    dense_hits: list[RetrievedChunk],
    sparse_hits: list[RetrievedChunk],
    *,
    k: int,
) -> list[RetrievedChunk]:
    """Reciprocal rank fusion of dense (Qdrant) and sparse (BM25) lists."""
    scores: dict[str, float] = {}
    by_key: dict[str, RetrievedChunk] = {}

    for rank, hit in enumerate(dense_hits):
        key = _chunk_fusion_key(hit)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        by_key[key] = hit

    for rank, hit in enumerate(sparse_hits):
        key = _chunk_fusion_key(hit)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key not in by_key or hit.score > by_key[key].score:
            by_key[key] = hit

    fused = sorted(by_key.values(), key=lambda h: scores[_chunk_fusion_key(h)], reverse=True)
    if not fused:
        return dense_hits
    max_rrf = max(scores.values()) or 1.0
    for hit in fused:
        hit.score = scores[_chunk_fusion_key(hit)] / max_rrf
    return fused


def _bm25_search(query: str, *, top_k: int) -> list[RetrievedChunk]:
    from app.retrieval.bm25_index import get_bm25_index

    index = get_bm25_index()
    if not index.records:
        return []
    raw = index.search(query, top_k=top_k)
    if not raw:
        return []
    max_score = max(score for _, score in raw) or 1.0
    return [_bm25_to_chunk(rec, score / max_score) for rec, score in raw]


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


def _chunk_from_formulation_record(record, *, score: float) -> RetrievedChunk:
    """Build a formula-shaped chunk from SQLite when Qdrant has no formulation_id point."""
    lines = [
        f"Formula: {record.name}",
        f"Product types: {', '.join(record.product_types)}",
        f"Ingredients ({len(record.ingredients)}):",
    ]
    for ing in (record.ingredients or [])[:16]:
        amt = ""
        if ing.amount is not None:
            unit = f" {ing.unit}" if ing.unit else ""
            amt = f" {ing.amount}{unit}"
        lines.append(f"- {ing.raw_name}{amt}")
    if record.procedure:
        lines.append("Procedure:")
        lines.extend(f"- {step}" for step in record.procedure[:6])
    text = "\n".join(lines)
    if record.source_text and len(text) < 400:
        text = f"{text}\n{record.source_text[:600]}"
    return RetrievedChunk(
        doc_id=record.doc_id,
        doc_title=record.doc_title or record.doc_id,
        pdf_page=int(record.pdf_page or 0),
        printed_page=record.printed_page,
        chunk_index=0,
        text=text,
        score=score,
        chunk_type="formula",
        section_title=record.name,
        product_types=list(record.product_types or []),
        text_hash="",
        formulation_id=record.id,
        ingredient_count=len(record.ingredients or []),
        extraction_confidence=float(record.confidence or 0.0),
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
    candidates = []
    for ranked in struct.matches[:3]:
        if ranked.score < 50:
            continue
        fid = ranked.record.id
        if fid and fid not in seen_fids:
            candidates.append(ranked)
            seen_fids.add(fid)

    if not candidates:
        return results

    ids_to_fetch = [c.record.id for c in candidates]
    payloads = fetch_chunks_by_formulation_ids(ids_to_fetch)
    payload_by_fid = {
        str(p.get("formulation_id")): p
        for p in payloads
        if p and p.get("formulation_id")
    }

    injected: list[RetrievedChunk] = []
    for i, ranked in enumerate(candidates):
        score = 0.94 - i * 0.02
        payload = payload_by_fid.get(ranked.record.id)
        if payload:
            injected.append(_chunk_from_payload(payload, score=score))
        else:
            # Rare types often exist in SQLite without a linked Qdrant formula point.
            injected.append(_chunk_from_formulation_record(ranked.record, score=score))

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
    intent: QueryIntent | None = None,
) -> list[RetrievedChunk]:
    if not query or not query.strip():
        return []

    intent = intent or parse_query_intent(query)
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

    # Pull rare-type tagged chunks into the pool (many were previously untagged).
    for rare in ("makeup", "deodorant", "toner", "soap", "cleanser", "gel"):
        if rare not in intent.product_types:
            continue
        rare_filter = qm.Filter(
            must=[
                qm.FieldCondition(key="product_types", match=qm.MatchValue(value=rare))
            ]
        )
        rare_hits = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector.tolist(),
            query_filter=rare_filter,
            limit=min(effective_fetch, 30),
            with_payload=True,
        ).points
        seen_ids = {f"{r.doc_id}:{r.pdf_page}:{r.chunk_index}" for r in results}
        for hit in rare_hits:
            key = f"{hit.payload.get('doc_id')}:{hit.payload.get('pdf_page')}:{hit.payload.get('chunk_index')}"
            if key not in seen_ids:
                results.append(_hit_to_chunk(hit, float(hit.score or 0.0)))
                seen_ids.add(key)

    results = _inject_structured_formula_chunks(results, query, intent)
    results = _dedup_hits(results)

    if settings.enable_bm25_hybrid:
        sparse = _bm25_search(query, top_k=settings.bm25_fetch_k)
        if sparse:
            results = _rrf_fuse(results, sparse, k=settings.hybrid_rrf_k)
            results = _dedup_hits(results)

    results = _rerank(results, query, intent)
    results = _prefer_on_type_formulas(results, query, intent)
    results = results[:top_k]

    logger.info(
        "Retrieved %d chunks for query (top score=%.3f, filter=%s)",
        len(results),
        results[0].score if results else 0.0,
        bool(qfilter),
    )
    return results
