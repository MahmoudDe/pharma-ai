"""Pydantic models for KBS validation reports."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["info", "warning", "error"]

RuleFamily = Literal["completeness", "consistency", "ranges", "fidelity", "regulatory"]

PrecisionStatus = Literal["verified", "review", "low_precision"]


class RuleFinding(BaseModel):
    rule_id: str
    family: RuleFamily
    severity: Severity
    message: str
    ingredient: str | None = None
    field: str | None = None
    observed: str | None = None
    expected: str | None = None


class FamilyScore(BaseModel):
    family: RuleFamily
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    error_count: int = 0
    warning_count: int = 0


class ValidationReport(BaseModel):
    formulation_id: str
    formulation_name: str = ""
    precision_score: float = Field(ge=0.0, le=1.0)
    status: PrecisionStatus
    family_scores: list[FamilyScore] = Field(default_factory=list)
    findings: list[RuleFinding] = Field(default_factory=list)
    compliance_status: Literal["pass", "warn", "fail", "skipped"] = "skipped"
    extraction_method: str = ""
    extraction_confidence: float = 0.0
    rescored_confidence: float | None = None
    rules_run: int = 0
    validated_at: str = ""

    def errors(self) -> list[RuleFinding]:
        return [f for f in self.findings if f.severity == "error"]

    def warnings(self) -> list[RuleFinding]:
        return [f for f in self.findings if f.severity == "warning"]
