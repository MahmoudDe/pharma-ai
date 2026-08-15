"""Query routing with structured-first search and tiered fallbacks."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.config import get_settings
from app.formulation.schemas import FormulationRecord
from app.formulation.search import (
    StructuredSearchResult,
    structured_search,
    structured_search_for_compare,
)
from app.formulation.store import get_formulation
from app.reasoning.llm import reason, reason_stream
from app.reasoning.prompt import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_STREAM,
    format_context,
    format_conversation_history,
    format_structured_formulations,
)
from app.reasoning.query_expand import expand_query
from app.reasoning.query_rewrite import rewrite_search_query
from app.reasoning.templates import (
    format_compare_response,
    format_lookup_response,
    format_transparent_failure,
)
from app.reasoning.brief import apply_brief_filters, format_structured_brief, merge_intent_with_brief
from app.reasoning.validate import validate_response
from app.retrieval.intent import (
    QueryClassification,
    QueryRoute,
    classify_query,
    parse_query_intent,
)
from app.retrieval.arabic_query import english_search_query
from app.retrieval.query_signals import extract_query_signals, record_matches_signals
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


def _kbs_annotations(
    records: list[FormulationRecord],
) -> dict[str, tuple[float, str, list[str]]]:
    """id -> (precision_score, status, top warning messages); best-effort."""
    try:
        from app.kbs import report_store

        verdicts = report_store.get_verdicts([r.id for r in records])
        annotations: dict[str, tuple[float, str, list[str]]] = {}
        for record in records:
            verdict = verdicts.get(record.id)
            if not verdict:
                continue
            score, status = verdict
            warnings: list[str] = []
            if status != "verified":
                report = report_store.get_report(record.id)
                if report:
                    warnings = [f.message for f in report.errors()[:2]]
                    if not warnings:
                        warnings = [f.message for f in report.warnings()[:2]]
            annotations[record.id] = (score, status, warnings)
        return annotations
    except Exception:  # KBS must never break the chat path
        logger.exception("KBS annotation lookup failed")
        return {}


def _structured_view(
    record: FormulationRecord,
    annotation: tuple[float, str, list[str]] | None = None,
) -> StructuredFormulationView:
    return StructuredFormulationView(
        formulation_id=record.id,
        name=record.name,
        product_types=record.product_types,
        doc_id=record.doc_id,
        pdf_page=record.pdf_page,
        printed_page=record.printed_page,
        confidence=record.confidence,
        precision_score=annotation[0] if annotation else None,
        kbs_status=annotation[1] if annotation else None,
        kbs_warnings=annotation[2] if annotation else [],
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
                # PDF deep-links require the slug doc_id, not the human title.
                document_id=chunk.doc_id or chunk.doc_title,
                document_title=chunk.doc_title or None,
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
    actions = [
        SuggestedNextAction(
            type="scale_to_batch",
            label="Scale to a 5 kg batch",
            payload={"batch_kg": 5},
        ),
    ]
    msg = (payload.message or "").lower()
    if "instead of" in msg or "substitute" in msg or "alternative" in msg:
        actions.append(
            SuggestedNextAction(
                type="substitute_ingredient",
                label="Suggest ingredient substitutions",
                payload={"message": payload.message},
            )
        )
    return actions


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
    rewritten_query: str | None = None,
) -> ChatTurnResponse:
    annotations = _kbs_annotations(structured_records[:5])
    views = [_structured_view(r, annotations.get(r.id)) for r in structured_records[:5]]
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
        rewritten_query=rewritten_query,
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
    rewritten_query: str | None = None,
    on_token: Callable[[str], None] | None = None,
) -> RoutedResponse:
    settings = get_settings()
    history_block = format_conversation_history(
        payload.history or [],
        max_messages=settings.chat_history_max_messages,
    )
    context_block = format_context(chunks)
    if history_block:
        context_block = f"{history_block}\n\n{context_block}"
    structured_block = format_structured_formulations(structured, _kbs_annotations(structured))
    brief_block = format_structured_brief(payload.structured_brief)
    if brief_block:
        context_block = f"{brief_block}\n\n{context_block}"
    if structured_block:
        context_block = f"{context_block}\n\n{structured_block}"

    if on_token is not None:
        llm_result = reason_stream(
            system_prompt=SYSTEM_PROMPT_STREAM,
            context_block=context_block,
            user_message=query,
            on_token=on_token,
        )
    else:
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
            rewritten_query=rewritten_query,
        ),
        classification=classify_query(query),
        chunks=chunks,
        llm_used=True,
        fallback_stage=fallback_stage,
    )


def _vector_search_ok(chunks: list[RetrievedChunk]) -> bool:
    settings = get_settings()
    return bool(chunks) and chunks[0].score >= settings.min_vector_score


def _direct_template_ok(
    route: QueryRoute,
    records: list[FormulationRecord],
    query: str,
) -> bool:
    """Only skip LLM when structured results satisfy explicit query constraints."""
    if not records:
        return False
    signals = extract_query_signals(query)
    if signals.asks_ingredient_role or signals.asks_advice:
        return False
    if signals.asks_identify_with_ingredients and signals.required_ingredients:
        return record_matches_signals(records[0], signals)
    if signals.required_ingredients and not record_matches_signals(records[0], signals):
        return False
    if route == "compare":
        if signals.compare_targets and len(records) < 2:
            return False
        if signals.compare_targets:
            for target, rec in zip(signals.compare_targets[:2], records[:2]):
                from app.retrieval.query_signals import fuzzy_name_match

                if not fuzzy_name_match(target, rec.name):
                    return False
    titles = signals.named_formulas
    if titles and len(titles) == 1:
        from app.retrieval.query_signals import fuzzy_name_match

        if not fuzzy_name_match(titles[0], records[0].name):
            return False
    return True


def route_chat(
    payload: ChatTurnRequest,
    *,
    on_token: Callable[[str], None] | None = None,
) -> RoutedResponse:
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
    rewritten, was_rewritten = rewrite_search_query(query, payload.history or [])
    search_query = english_search_query(rewritten)
    rewritten_label = search_query if was_rewritten else None
    classification = classify_query(search_query)
    route = classification.route
    intent = merge_intent_with_brief(classification.intent, payload.structured_brief)
    signals = extract_query_signals(search_query)

    logger.info(
        "Route=%s query=%r search=%r rewritten=%s",
        route,
        query[:80],
        search_query[:80],
        was_rewritten,
    )

    # Chitchat / meta / off-topic: do not recycle the previous formula from hybrid search.
    if (
        route == "unknown"
        and not intent.wants_formula
        and not intent.product_types
        and not payload.structured_brief
    ):
        return RoutedResponse(
            response=_build_response(
                message=(
                    "Ask me for a cosmetic formula (for example: baby shampoo, "
                    "hand cream, or sulfate-free shampoo) and I will pull a cited "
                    "recipe from the library."
                ),
                route="unknown",
                llm_used=False,
                structured_records=[],
                chunks=[],
                search_confidence=None,
                fallback_stage="none",
                payload=payload,
                rewritten_query=rewritten_label,
            ),
            classification=classification,
        )

    if route == "reasoning":
        chunks = search(search_query, top_k=TOP_K, intent=intent)
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
                    rewritten_query=rewritten_label,
                ),
                classification=classification,
                fallback_stage="failed",
            )
        return _run_llm_path(
            query,
            chunks,
            structured,
            "reasoning",
            payload,
            fallback_stage="none",
            rewritten_query=rewritten_label,
            on_token=on_token,
        )

    limit = 5 if route == "compare" else 3
    struct_result = structured_search(
        search_query, intent, limit=limit, brief=payload.structured_brief
    )
    structured_records = apply_brief_filters(
        [m.record for m in struct_result.matches],
        payload.structured_brief,
    )

    if route == "compare" and len(signals.compare_targets) >= 2:
        compare_records = structured_search_for_compare(
            search_query,
            intent,
            signals,
            limit=limit,
            brief=payload.structured_brief,
        )
        if len(compare_records) >= 2:
            structured_records = apply_brief_filters(
                compare_records,
                payload.structured_brief,
            )
            struct_result = StructuredSearchResult(
                matches=struct_result.matches,
                top_confidence=max(struct_result.top_confidence, 85.0),
                route_hint="direct",
            )

    fallback_stage: FallbackStage = "none"

    use_direct = (
        struct_result.route_hint == "direct"
        and structured_records
        and not (route == "compare" and len(structured_records) < 2)
        and _direct_template_ok(route, structured_records, search_query)
    )

    if use_direct:
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
                rewritten_query=rewritten_label,
            ),
            classification=classification,
            structured_result=struct_result,
            llm_used=False,
        )

    chunks = search(search_query, top_k=TOP_K, intent=intent)
    hydrated = apply_brief_filters(_hydrate_chunks(chunks), payload.structured_brief)
    if not structured_records:
        structured_records = hydrated

    if struct_result.route_hint == "hybrid" and structured_records:
        needs_llm = (
            signals.asks_ingredient_role
            or signals.asks_advice
            or signals.asks_identify_with_ingredients
            or (route == "compare" and len(structured_records) >= 2)
            or not _direct_template_ok(route, structured_records, search_query)
        )
        if settings.use_llm_on_hybrid or needs_llm:
            return _run_llm_path(
                query,
                chunks,
                structured_records,
                route,
                payload,
                fallback_stage="none",
                search_confidence=struct_result.top_confidence,
                rewritten_query=rewritten_label,
                on_token=on_token,
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
                rewritten_query=rewritten_label,
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
                rewritten_query=rewritten_label,
                on_token=on_token,
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
                rewritten_query=rewritten_label,
            ),
            classification=classification,
            structured_result=struct_result,
            chunks=chunks,
            fallback_stage="vector",
        )

    if settings.enable_query_expansion:
        fallback_stage = "expanded"
        for alt in expand_query(search_query)[1:]:
            alt_intent = merge_intent_with_brief(
                parse_query_intent(alt), payload.structured_brief
            )
            struct_alt = structured_search(
                alt, alt_intent, limit=limit, brief=payload.structured_brief
            )
            if struct_alt.matches:
                recs = apply_brief_filters(
                    [m.record for m in struct_alt.matches],
                    payload.structured_brief,
                )
                return RoutedResponse(
                    response=_build_response(
                        message=format_lookup_response(recs),
                        route=route,
                        llm_used=False,
                        structured_records=recs,
                        chunks=search(alt, top_k=TOP_K, intent=alt_intent),
                        search_confidence=struct_alt.top_confidence,
                        fallback_stage="expanded",
                        payload=payload,
                        rewritten_query=rewritten_label,
                    ),
                    classification=classification,
                    fallback_stage="expanded",
                )
            chunks_alt = search(alt, top_k=TOP_K, intent=alt_intent)
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
                        rewritten_query=rewritten_label,
                    ),
                    classification=classification,
                    chunks=chunks_alt,
                    fallback_stage="expanded",
                )

    fallback_stage = "failed"
    partial = apply_brief_filters(
        list_formulations_fallback(structured_records, intent),
        payload.structured_brief,
    )
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
            rewritten_query=rewritten_label,
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

