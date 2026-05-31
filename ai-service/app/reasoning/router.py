"""Query routing with structured-first search and tiered fallbacks."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from app.config import get_settings
from app.formulation.schemas import FormulationRecord
from app.formulation.search import StructuredSearchResult, structured_search
from app.formulation.store import get_formulation
from app.reasoning.llm import reason
from app.reasoning.prompt import SYSTEM_PROMPT, format_context, format_structured_formulations
from app.reasoning.query_expand import expand_query
from app.reasoning.templates import (
    format_compare_response,
    format_lookup_response,
    format_transparent_failure,
)
from app.reasoning.validate import validate_response
from app.retrieval.intent import (
    QueryClassification,
    QueryRoute,
    classify_query,
    parse_query_intent,
)
from app.retrieval.search import RetrievedChunk, search
from app.schemas import (
    ChatTurnRequest,
    ChatTurnResponse,
    CitedEvidence,
    StructuredFormulationView,
    SuggestedNextAction,
)


logger = logging.getLogger(__name__)

TOP_K = 10
QUOTE_MAX_CHARS = 280
FallbackStage = Literal["none", "vector", "expanded", "failed"]


@dataclass
class RoutedResponse:
    response: ChatTurnResponse
    classification: QueryClassification
    structured_result: StructuredSearchResult | None = None
    chunks: list[RetrievedChunk] = field(default_factory=list)
    llm_used: bool = False
    fallback_stage: FallbackStage = "none"


def _structured_view(record: FormulationRecord) -> StructuredFormulationView:
    return StructuredFormulationView(
        formulation_id=record.id,
        name=record.name,
        product_types=record.product_types,
        doc_id=record.doc_id,
        pdf_page=record.pdf_page,
        printed_page=record.printed_page,
        confidence=record.confidence,
        ingredients=[
            {
                "raw_name": ing.raw_name,
                "normalized_name": ing.normalized_name,
                "amount": ing.amount,
                "unit": ing.unit,
                "phase": ing.phase,
            }
            for ing in record.ingredients
        ],
        procedure=record.procedure,
    )


def _hydrate_chunks(chunks: list[RetrievedChunk]) -> list[FormulationRecord]:
    seen: set[str] = set()
    out: list[FormulationRecord] = []
    for ch in chunks:
        if not ch.formulation_id or ch.formulation_id in seen:
            continue
        rec = get_formulation(ch.formulation_id)
        if rec:
            seen.add(ch.formulation_id)
            out.append(rec)
    return out


def _evidence_from_chunks(
    chunks: list[RetrievedChunk],
    structured: list[FormulationRecord],
) -> list[CitedEvidence]:
    evidence: list[CitedEvidence] = []
    for i, chunk in enumerate(chunks[:5]):
        snippet = chunk.text.strip()[:QUOTE_MAX_CHARS]
        fid = chunk.formulation_id
        if not fid and structured:
            fid = structured[0].id if i == 0 else None
        evidence.append(
            CitedEvidence(
                document_id=chunk.doc_title or chunk.doc_id,
                page=chunk.page,
                pdf_page=chunk.pdf_page,
                printed_page=chunk.printed_page,
                quote=snippet,
                confidence="high" if chunk.score >= 0.7 else "medium" if chunk.score >= 0.5 else "low",
                formulation_id=fid,
                quote_verified=bool(fid),
            )
        )
    return evidence


def _default_actions(payload: ChatTurnRequest) -> list[SuggestedNextAction]:
    return [
        SuggestedNextAction(
            type="scale_to_batch",
            label="Scale to a 5 kg batch",
            payload={"batch_kg": 5},
        ),
    ]


def _build_response(
    *,
    message: str,
    route: QueryRoute,
    llm_used: bool,
    structured_records: list[FormulationRecord],
    chunks: list[RetrievedChunk],
    search_confidence: float | None,
    fallback_stage: FallbackStage,
    payload: ChatTurnRequest,
) -> ChatTurnResponse:
    views = [_structured_view(r) for r in structured_records[:5]]
    return ChatTurnResponse(
        assistant_message=message,
        cited_evidence=_evidence_from_chunks(chunks, structured_records),
        suggested_next_actions=_default_actions(payload),
        structured_formulation=views[0] if len(views) == 1 else None,
        structured_formulations=views,
        route=route,
        llm_used=llm_used,
        search_confidence=search_confidence,
        fallback_stage=fallback_stage,
    )


def _run_llm_path(
    query: str,
    chunks: list[RetrievedChunk],
    structured: list[FormulationRecord],
    route: QueryRoute,
    payload: ChatTurnRequest,
    *,
    fallback_stage: FallbackStage = "none",
    search_confidence: float | None = None,
) -> RoutedResponse:
    context_block = format_context(chunks)
    structured_block = format_structured_formulations(structured)
    if structured_block:
        context_block = f"{context_block}\n\n{structured_block}"

    llm_result = reason(
        system_prompt=SYSTEM_PROMPT,
        context_block=context_block,
        user_message=query,
    )
    validated = validate_response(llm_result, chunks)
    answer = validated.answer or "I could not synthesise an answer from the sources."

    return RoutedResponse(
        response=_build_response(
            message=answer,
            route=route,
            llm_used=True,
            structured_records=structured,
            chunks=chunks,
            search_confidence=search_confidence,
            fallback_stage=fallback_stage,
            payload=payload,
        ),
        classification=classify_query(query),
        chunks=chunks,
        llm_used=True,
        fallback_stage=fallback_stage,
    )


def _vector_search_ok(chunks: list[RetrievedChunk]) -> bool:
    settings = get_settings()
    return bool(chunks) and chunks[0].score >= settings.min_vector_score


def route_chat(payload: ChatTurnRequest) -> RoutedResponse:
    query = payload.message.strip()
    if not query:
        return RoutedResponse(
            response=ChatTurnResponse(
                assistant_message="Please send a non-empty question.",
                route="unknown",
                llm_used=False,
            ),
            classification=classify_query(""),
        )

    settings = get_settings()
    classification = classify_query(query)
    route = classification.route
    intent = classification.intent

    logger.info("Route=%s query=%r", route, query[:80])

    if route == "reasoning":
        chunks = search(query, top_k=TOP_K)
        structured = _hydrate_chunks(chunks)
        if not _vector_search_ok(chunks) and not structured:
            return RoutedResponse(
                response=_build_response(
                    message=format_transparent_failure(query, [], []),
                    route="reasoning",
                    llm_used=False,
                    structured_records=[],
                    chunks=[],
                    search_confidence=None,
                    fallback_stage="failed",
                    payload=payload,
                ),
                classification=classification,
                fallback_stage="failed",
            )
        return _run_llm_path(
            query, chunks, structured, "reasoning", payload, fallback_stage="none"
        )

    limit = 5 if route == "compare" else 3
    struct_result = structured_search(query, intent, limit=limit)
    structured_records = [m.record for m in struct_result.matches]
    fallback_stage: FallbackStage = "none"

    if (
        struct_result.route_hint == "direct"
        and structured_records
        and not (route == "compare" and len(structured_records) < 2)
    ):
        if route == "compare":
            msg = format_compare_response(structured_records)
        else:
            msg = format_lookup_response(structured_records)
        return RoutedResponse(
            response=_build_response(
                message=msg,
                route=route,
                llm_used=False,
                structured_records=structured_records,
                chunks=[],
                search_confidence=struct_result.top_confidence,
                fallback_stage="none",
                payload=payload,
            ),
            classification=classification,
            structured_result=struct_result,
            llm_used=False,
        )

    chunks = search(query, top_k=TOP_K)
    hydrated = _hydrate_chunks(chunks)
    if not structured_records:
        structured_records = hydrated

    if struct_result.route_hint == "hybrid" and structured_records:
        if settings.use_llm_on_hybrid:
            return _run_llm_path(
                query,
                chunks,
                structured_records,
                route,
                payload,
                fallback_stage="none",
                search_confidence=struct_result.top_confidence,
            )
        msg = format_lookup_response(structured_records)
        if chunks:
            msg += "\n\n**Additional context from references:**\n"
            msg += chunks[0].text[:400].strip() + "…"
        return RoutedResponse(
            response=_build_response(
                message=msg,
                route=route,
                llm_used=False,
                structured_records=structured_records,
                chunks=chunks,
                search_confidence=struct_result.top_confidence,
                fallback_stage="none",
                payload=payload,
            ),
            classification=classification,
            structured_result=struct_result,
            chunks=chunks,
        )

    fallback_stage = "vector"
    if _vector_search_ok(chunks):
        if settings.use_llm_on_vector_fallback:
            return _run_llm_path(
                query,
                chunks,
                structured_records,
                route,
                payload,
                fallback_stage="vector",
                search_confidence=struct_result.top_confidence,
            )
        titles = [
            (c.section_title or c.text[:60].replace("\n", " "))
            for c in chunks[:3]
        ]
        msg = format_transparent_failure(query, structured_records, titles)
        if route == "lookup" and hydrated:
            msg = format_lookup_response(hydrated[:1]) + "\n\n" + msg
        return RoutedResponse(
            response=_build_response(
                message=msg,
                route=route if route != "unknown" else "lookup",
                llm_used=False,
                structured_records=hydrated or structured_records,
                chunks=chunks,
                search_confidence=struct_result.top_confidence,
                fallback_stage="vector",
                payload=payload,
            ),
            classification=classification,
            structured_result=struct_result,
            chunks=chunks,
            fallback_stage="vector",
        )

    if settings.enable_query_expansion:
        fallback_stage = "expanded"
        for alt in expand_query(query)[1:]:
            struct_alt = structured_search(alt, parse_query_intent(alt), limit=limit)
            if struct_alt.matches:
                recs = [m.record for m in struct_alt.matches]
                return RoutedResponse(
                    response=_build_response(
                        message=format_lookup_response(recs),
                        route=route,
                        llm_used=False,
                        structured_records=recs,
                        chunks=search(alt, top_k=TOP_K),
                        search_confidence=struct_alt.top_confidence,
                        fallback_stage="expanded",
                        payload=payload,
                    ),
                    classification=classification,
                    fallback_stage="expanded",
                )
            chunks_alt = search(alt, top_k=TOP_K)
            if _vector_search_ok(chunks_alt):
                return RoutedResponse(
                    response=_build_response(
                        message=format_transparent_failure(
                            query,
                            structured_records,
                            [(c.section_title or c.text[:50]) for c in chunks_alt[:3]],
                        ),
                        route=route,
                        llm_used=False,
                        structured_records=_hydrate_chunks(chunks_alt),
                        chunks=chunks_alt,
                        search_confidence=struct_alt.top_confidence,
                        fallback_stage="expanded",
                        payload=payload,
                    ),
                    classification=classification,
                    chunks=chunks_alt,
                    fallback_stage="expanded",
                )

    fallback_stage = "failed"
    partial = list_formulations_fallback(structured_records, intent)
    return RoutedResponse(
        response=_build_response(
            message=format_transparent_failure(
                query,
                partial,
                [(c.section_title or "") for c in chunks[:3] if c.section_title],
            ),
            route=route if route != "unknown" else "fallback",
            llm_used=False,
            structured_records=partial,
            chunks=chunks,
            search_confidence=struct_result.top_confidence,
            fallback_stage="failed",
            payload=payload,
        ),
        classification=classification,
        structured_result=struct_result,
        chunks=chunks,
        fallback_stage="failed",
    )


def list_formulations_fallback(
    existing: list[FormulationRecord],
    intent,
) -> list[FormulationRecord]:
    from app.formulation.store import list_formulations

    if existing:
        return existing[:3]
    return list_formulations(product_types=intent.product_types or None, limit=3)

