from __future__ import annotations

import logging

from app.kbs.config import get_kbs_config
from app.kbs.facts import FactContext
from app.kbs.rules.base import Rule
from app.kbs.schemas import FamilyScore, PrecisionStatus, RuleFinding


logger = logging.getLogger(__name__)


def run_rules(facts: FactContext, rules: list[Rule]) -> tuple[list[RuleFinding], int]:
    findings: list[RuleFinding] = []
    executed = 0
    for rule in rules:
        try:
            findings.extend(rule.check(facts))
            executed += 1
        except Exception:  # one broken rule must never sink the whole validation
            logger.exception(
                "KBS rule %s failed on formulation %s",
                getattr(rule, "rule_id", type(rule).__name__),
                facts.record.id,
            )
    return findings, executed


def score_findings(findings: list[RuleFinding]) -> tuple[float, list[FamilyScore]]:
    config = get_kbs_config()
    weights: dict[str, float] = config["weights"]
    penalties: dict[str, float] = config["penalties"]

    family_scores: list[FamilyScore] = []
    total = 0.0
    for family, weight in weights.items():
        family_findings = [f for f in findings if f.family == family]
        penalty = sum(penalties.get(f.severity, 0.0) for f in family_findings)
        score = max(0.0, 1.0 - penalty)
        family_scores.append(
            FamilyScore(
                family=family,
                score=round(score, 4),
                weight=weight,
                error_count=sum(1 for f in family_findings if f.severity == "error"),
                warning_count=sum(1 for f in family_findings if f.severity == "warning"),
            )
        )
        total += weight * score

    weight_sum = sum(weights.values()) or 1.0
    return round(total / weight_sum, 4), family_scores


def status_for_score(score: float, findings: list[RuleFinding] | None = None) -> PrecisionStatus:
    bands = get_kbs_config()["bands"]
    if score < float(bands["low_precision_below"]):
        return "low_precision"
    if score < float(bands["review_below"]):
        return "review"
    # "verified" is a hard claim: a weighted average must not wash out a
    # precision error (e.g. percentages summing to 217%). Any error in a
    # precision family caps the record at "review".
    if findings and any(f.severity == "error" and f.family != "regulatory" for f in findings):
        return "review"
    return "verified"
