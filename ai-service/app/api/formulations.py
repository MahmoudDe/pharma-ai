from fastapi import APIRouter, HTTPException, Query

from app.formulation.schemas import (
    FormulationRecord,
    FormulationSearchRequest,
    StructuredFormulationSummary,
)
from app.formulation.store import get_formulation, list_formulations


router = APIRouter(prefix="/formulations", tags=["formulations"])


def _to_summary(record: FormulationRecord) -> StructuredFormulationSummary:
    return StructuredFormulationSummary(
        formulation_id=record.id,
        name=record.name,
        product_types=record.product_types,
        doc_id=record.doc_id,
        pdf_page=record.pdf_page,
        printed_page=record.printed_page,
        ingredient_count=len(record.ingredients),
        confidence=record.confidence,
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
    return {
        "formulations": [_to_summary(r) for r in records],
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
