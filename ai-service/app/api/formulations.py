from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.formulation.cost import estimate_formulation_cost, merge_price_rows, parse_price_csv, price_table_stats
from app.formulation.compare import compare_formulations
from app.formulation.regulatory import check_formulation
from app.formulation.review import list_review_queue, patch_formulation
from app.formulation.schemas import (
    FormulationRecord,
    FormulationSearchRequest,
    IngredientLine,
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
    include_llm_note: bool = False


class ComplianceRequest(BaseModel):
    markets: list[str] = Field(default_factory=lambda: ["EU"])


class CompareRequest(BaseModel):
    left_id: str
    right_id: str
    markets: list[str] | None = None


class FormulationPatchRequest(BaseModel):
    name: str | None = None
    ingredients: list[IngredientLine] | None = None
    procedure: list[str] | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)


def _to_summary(
    record: FormulationRecord,
    verdicts: dict[str, tuple[float, str]] | None = None,
) -> StructuredFormulationSummary:
    verdict = (verdicts or {}).get(record.id)
    cost = estimate_formulation_cost(record)
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
        estimated_cost_per_kg=cost.cost_per_kg,
        cost_coverage_percent=round(cost.covered_percent * 100, 1) if cost.covered_percent else None,
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


@router.get("/review")
def review_queue(
    confidence_max: float = Query(0.75, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    items = list_review_queue(confidence_max=confidence_max, limit=limit)
    return {"formulations": items, "count": len(items)}


@router.get("/{formulation_id}")
def get_one(formulation_id: str) -> FormulationRecord:
    record = get_formulation(formulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    return record


@router.patch("/{formulation_id}")
def patch_one(formulation_id: str, body: FormulationPatchRequest) -> FormulationRecord:
    try:
        return patch_formulation(
            formulation_id,
            name=body.name,
            ingredients=body.ingredients,
            procedure=body.procedure,
            confidence=body.confidence,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Formulation not found") from None


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


@router.post("/compare")
def compare_two(body: CompareRequest) -> dict:
    left = get_formulation(body.left_id)
    right = get_formulation(body.right_id)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    report = compare_formulations(left, right, markets=body.markets)
    return {
        "left_id": report.left_id,
        "right_id": report.right_id,
        "left_name": report.left_name,
        "right_name": report.right_name,
        "left_cost_per_kg": report.left_cost_per_kg,
        "right_cost_per_kg": report.right_cost_per_kg,
        "cost_delta_per_kg": report.cost_delta_per_kg,
        "left_compliance": report.left_compliance,
        "right_compliance": report.right_compliance,
        "markets": report.markets,
        "only_in_left": report.only_in_left,
        "only_in_right": report.only_in_right,
        "ingredient_deltas": [
            {
                "key": d.key,
                "raw_name": d.raw_name,
                "left_amount": d.left_amount,
                "left_unit": d.left_unit,
                "right_amount": d.right_amount,
                "right_unit": d.right_unit,
            }
            for d in report.ingredient_deltas
        ],
        "role_summaries": [
            {
                "role": r.role,
                "left_count": r.left_count,
                "right_count": r.right_count,
                "left_examples": r.left_examples,
                "right_examples": r.right_examples,
            }
            for r in report.role_summaries
        ],
        "summary_lines": report.summary_lines,
    }


@router.get("/prices")
def ingredient_prices() -> dict:
    return price_table_stats()


@router.post("/prices/upload")
async def upload_prices(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 CSV.") from None
    rows = parse_price_csv(text)
    if not rows:
        raise HTTPException(status_code=400, detail="No valid price rows found.")
    count = merge_price_rows(rows)
    return {"merged_count": count, **price_table_stats()}


@router.get("/{formulation_id}/cost")
def formulation_cost(formulation_id: str) -> dict:
    record = get_formulation(formulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    est = estimate_formulation_cost(record)
    return {
        "formulation_id": formulation_id,
        "cost_per_kg": est.cost_per_kg,
        "currency": est.currency,
        "covered_percent": est.covered_percent,
        "missing_ingredients": est.missing_ingredients,
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
        include_llm_note=body.include_llm_note,
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
