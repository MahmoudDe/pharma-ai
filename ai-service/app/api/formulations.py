from fastapi import APIRouter, HTTPException, Query

from app.formulation.regulatory import check_formulation
from app.formulation.schemas import (
    FormulationRecord,
    FormulationSearchRequest,
    StructuredFormulationSummary,
)
from app.formulation.store import get_formulation, list_formulations
from app.kbs.report_store import get_verdicts
from app.formulation.substitution import suggest_substitutions
from app.schemas import StructuredBrief
from pydantic import BaseModel, Field


router = APIRouter(prefix="/formulations", tags=["formulations"])


class SubstitutionRequest(BaseModel):
    ingredient: str
    constraints: StructuredBrief | None = None


class ComplianceRequest(BaseModel):
    markets: list[str] = Field(default_factory=lambda: ["EU"])


def _to_summary(
    record: FormulationRecord,
    verdicts: dict[str, tuple[float, str]] | None = None,
) -> StructuredFormulationSummary:
    verdict = (verdicts or {}).get(record.id)
    return StructuredFormulationSummary(
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


@router.get("")
def list_all(
    product_type: str | None = Query(None),
    ingredient: str | None = Query(None),
    doc_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> dict:
    records = list_formulations(
        product_type=product_type,
        ingredient=ingredient,
        doc_id=doc_id,
        limit=limit,
    )
    verdicts = get_verdicts([r.id for r in records])
    return {
        "formulations": [_to_summary(r, verdicts) for r in records],
        "count": len(records),
    }


@router.get("/{formulation_id}")
def get_one(formulation_id: str) -> FormulationRecord:
    record = get_formulation(formulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    return record


@router.post("/search")
def search(body: FormulationSearchRequest) -> dict:
    records = list_formulations(
        product_type=body.product_type,
        ingredient=body.ingredient,
        doc_id=body.doc_id,
        limit=body.limit,
    )
    return {
        "formulations": records,
        "count": len(records),
    }


@router.post("/{formulation_id}/substitutions")
def substitutions(formulation_id: str, body: SubstitutionRequest) -> dict:
    record = get_formulation(formulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    suggestions = suggest_substitutions(
        record,
        body.ingredient,
        brief=body.constraints,
    )
    return {
        "suggestions": [
            {
                "substitute": s.substitute,
                "confidence": s.confidence,
                "reason": s.reason,
                "source": s.source,
                "citations": [c.model_dump() for c in s.citations],
            }
            for s in suggestions
        ]
    }


@router.post("/{formulation_id}/compliance")
def compliance(formulation_id: str, body: ComplianceRequest) -> dict:
    record = get_formulation(formulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    report = check_formulation(record, body.markets)
    return {
        "status": report.status,
        "markets": report.markets,
        "findings": [
            {
                "ingredient": f.ingredient,
                "normalized_name": f.normalized_name,
                "market": f.market,
                "status": f.status,
                "max_percent": f.max_percent,
                "source_ref": f.source_ref,
                "message": f.message,
            }
            for f in report.findings
        ],
    }
