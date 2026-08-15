from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.formulation.store import get_formulation
from app.kbs import report_store
from app.kbs.config import clear_config_cache
from app.kbs.registry import describe_rules
from app.kbs.rules.ranges import clear_ranges_cache
from app.kbs.schemas import ValidationReport
from app.kbs.service import validate_all, validate_and_rescore


router = APIRouter(prefix="/kbs", tags=["kbs"])


class ValidateRequest(BaseModel):
    markets: list[str] | None = None


class BatchValidateRequest(BaseModel):
    markets: list[str] | None = None
    limit: int = Field(default=10000, ge=1, le=100000)
    reload_knowledge: bool = Field(
        default=False,
        description="Re-read YAML knowledge files before validating.",
    )


@router.post("/validate/{formulation_id}")
def validate_one(formulation_id: str, body: ValidateRequest | None = None) -> ValidationReport:
    record = get_formulation(formulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formulation not found")
    markets = body.markets if body else None
    return validate_and_rescore(record, markets=markets)


@router.post("/validate-batch")
def validate_batch(body: BatchValidateRequest | None = None) -> dict:
    body = body or BatchValidateRequest()
    if body.reload_knowledge:
        clear_config_cache()
        clear_ranges_cache()
    return validate_all(markets=body.markets, limit=body.limit)


@router.get("/report/{formulation_id}")
def get_report(formulation_id: str) -> ValidationReport:
    report = report_store.get_report(formulation_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No KBS report for this formulation; run POST /kbs/validate/{id} first",
        )
    return report


@router.get("/rules")
def list_rules() -> dict:
    rules = describe_rules()
    return {"rules": rules, "count": len(rules)}


@router.get("/stats")
def stats() -> dict:
    return {"reports": report_store.count_reports()}
