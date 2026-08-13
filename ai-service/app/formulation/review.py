"""Review queue and manual correction for extracted formulations."""
from __future__ import annotations

from app.formulation.schemas import FormulationRecord, IngredientLine, StructuredFormulationSummary
from app.formulation.store import get_formulation, list_formulations, upsert_formulation
from app.kbs.report_store import get_verdicts, list_reports_by_status


def list_review_queue(
    *,
    confidence_max: float = 0.75,
    kbs_statuses: list[str] | None = None,
    limit: int = 50,
) -> list[StructuredFormulationSummary]:
    """Formulations needing human review (low confidence or weak KBS verdict)."""
    statuses = kbs_statuses or ["review", "low_precision"]
    kbs_rows = list_reports_by_status(statuses, limit=limit * 2)
    seen: set[str] = set()
    summaries: list[StructuredFormulationSummary] = []

    for formulation_id, score, status in kbs_rows:
        if formulation_id in seen:
            continue
        record = get_formulation(formulation_id)
        if record is None:
            continue
        seen.add(formulation_id)
        summaries.append(
            StructuredFormulationSummary(
                formulation_id=record.id,
                name=record.name,
                product_types=record.product_types,
                doc_id=record.doc_id,
                pdf_page=record.pdf_page,
                printed_page=record.printed_page,
                ingredient_count=len(record.ingredients),
                confidence=record.confidence,
                precision_score=score,
                kbs_status=status,
            )
        )
        if len(summaries) >= limit:
            return summaries

    low_conf = list_formulations(limit=limit * 4)
    for record in sorted(low_conf, key=lambda r: r.confidence):
        if record.id in seen:
            continue
        if record.confidence > confidence_max:
            continue
        verdict = get_verdicts([record.id]).get(record.id)
        summaries.append(
            StructuredFormulationSummary(
                formulation_id=record.id,
                name=record.name,
                product_types=record.product_types,
                doc_id=record.doc_id,
                pdf_page=record.pdf_page,
                printed_page=record.printed_page,
                ingredient_count=len(record.ingredients),
                confidence=record.confidence,
                precision_score=verdict[0] if verdict else None,
                kbs_status=verdict[1] if verdict else None,
            )
        )
        seen.add(record.id)
        if len(summaries) >= limit:
            break

    return summaries


def patch_formulation(
    formulation_id: str,
    *,
    name: str | None = None,
    ingredients: list[IngredientLine] | None = None,
    procedure: list[str] | None = None,
    confidence: float | None = None,
) -> FormulationRecord:
    record = get_formulation(formulation_id)
    if record is None:
        raise KeyError(formulation_id)

    if name is not None:
        record.name = name.strip() or record.name
    if ingredients is not None:
        record.ingredients = ingredients
    if procedure is not None:
        record.procedure = procedure
    if confidence is not None:
        record.confidence = confidence

    upsert_formulation(record)

    try:
        from app.kbs.service import validate_and_rescore

        validate_and_rescore(record)
    except Exception:
        pass

    return record
