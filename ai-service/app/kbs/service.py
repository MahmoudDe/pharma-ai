from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.formulation.regulatory import check_formulation
from app.formulation.schemas import FormulationRecord
from app.formulation.store import get_store
from app.formulation.store_base import FormulationSearchFilters
from app.kbs import report_store
from app.kbs.config import get_kbs_config
from app.kbs.engine import run_rules, score_findings, status_for_score
from app.kbs.facts import build_facts
from app.kbs.registry import get_rules
from app.kbs.schemas import RuleFinding, ValidationReport


logger = logging.getLogger(__name__)


def validate_record(
    record: FormulationRecord,
    *,
    markets: list[str] | None = None,
    persist: bool = True,
) -> ValidationReport:
    from app.kbs.chunks import fetch_indexed_chunk_texts

    facts = build_facts(
        record,
        indexed_chunk_texts=fetch_indexed_chunk_texts(record.id),
    )
    findings, rules_run = run_rules(facts, get_rules())
    precision_score, family_scores = score_findings(findings)

    compliance_status = "skipped"
    resolved_markets = markets if markets is not None else list(
        get_kbs_config()["regulatory_markets"]
    )
    if resolved_markets:
        try:
            compliance = check_formulation(record, resolved_markets)
            compliance_status = compliance.status
            for finding in compliance.findings:
                findings.append(
                    RuleFinding(
                        rule_id=f"regulatory.{finding.status}",
                        family="regulatory",
                        severity="error" if finding.status == "prohibited" else "warning",
                        message=finding.message,
                        ingredient=finding.ingredient,
                        observed=finding.status,
                        expected=finding.source_ref,
                    )
                )
        except Exception:
            logger.exception("Regulatory check failed for %s", record.id)

    report = ValidationReport(
        formulation_id=record.id,
        formulation_name=record.name,
        precision_score=precision_score,
        status=status_for_score(precision_score, findings),
        family_scores=family_scores,
        findings=findings,
        compliance_status=compliance_status,
        extraction_method=record.extraction_method,
        extraction_confidence=record.confidence,
        rescored_confidence=rescored_confidence(record, precision_score),
        rules_run=rules_run,
        validated_at=datetime.now(timezone.utc).isoformat(),
    )
    if persist:
        report_store.save_report(report)
    return report


def rescored_confidence(record: FormulationRecord, precision_score: float) -> float:
    """Blend extraction confidence with the KBS precision score (KBS-weighted)."""
    return round(0.4 * record.confidence + 0.6 * precision_score, 4)


def validate_and_rescore(
    record: FormulationRecord,
    *,
    markets: list[str] | None = None,
) -> ValidationReport:
    """Validate, persist the report, and write the rescored confidence back to the store."""
    report = validate_record(record, markets=markets, persist=True)
    if report.rescored_confidence is not None and abs(
        report.rescored_confidence - record.confidence
    ) >= 0.005:
        record.confidence = report.rescored_confidence
        try:
            get_store().upsert(record)
        except Exception:
            logger.exception("Could not persist rescored confidence for %s", record.id)
    return report


def validate_all(
    *,
    markets: list[str] | None = None,
    limit: int = 10000,
) -> dict:
    records = get_store().search(FormulationSearchFilters(limit=limit))
    counts = {"verified": 0, "review": 0, "low_precision": 0}
    for record in records:
        report = validate_and_rescore(record, markets=markets)
        counts[report.status] += 1
    logger.info(
        "KBS batch validation: %d records (%d verified / %d review / %d low precision)",
        len(records),
        counts["verified"],
        counts["review"],
        counts["low_precision"],
    )
    return {"validated": len(records), **counts}
