"""Regulatory / market compliance checks for formulations."""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import FormulationRecord


logger = logging.getLogger(__name__)

ComplianceStatus = Literal["pass", "warn", "fail"]

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "regulatory"


@dataclass(slots=True)
class ComplianceFinding:
    ingredient: str
    normalized_name: str
    market: str
    status: str
    max_percent: float | None
    source_ref: str
    message: str


@dataclass(slots=True)
class ComplianceReport:
    status: ComplianceStatus
    markets: list[str]
    findings: list[ComplianceFinding] = field(default_factory=list)


def _load_csv_rules() -> list[dict]:
    path = _DATA_DIR / "eu_restrictions.csv"
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def _load_json_rules() -> list[dict]:
    path = _DATA_DIR / "fda_prohibited.json"
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _ingredient_matches(ing_norm: str, ing_raw: str, rule_name: str, aliases: list[str]) -> bool:
    candidates = [rule_name.lower(), *[a.lower() for a in aliases]]
    raw = ing_raw.lower()
    for c in candidates:
        if not c:
            continue
        if c in ing_norm or c in raw or ing_norm in c or raw in c:
            return True
    return False


def check_formulation(record: FormulationRecord, markets: list[str]) -> ComplianceReport:
    markets_upper = [m.upper() for m in markets if m.strip()]
    if not markets_upper:
        return ComplianceReport(status="pass", markets=[])

    findings: list[ComplianceFinding] = []
    csv_rules = _load_csv_rules()
    json_rules = _load_json_rules()

    for ing in record.ingredients:
        ing_norm = (ing.normalized_name or normalize_ingredient_name(ing.raw_name) or ing.raw_name).lower()
        ing_raw = ing.raw_name or ""

        for rule in csv_rules:
            market = (rule.get("market") or "").upper()
            if market not in markets_upper:
                continue
            name = rule.get("ingredient", "")
            if not _ingredient_matches(ing_norm, ing_raw, name, []):
                continue
            status = (rule.get("status") or "").lower()
            max_pct = rule.get("max_percent")
            max_val = float(max_pct) if max_pct not in (None, "") else None
            amount = ing.amount if ing.unit == "%" else None
            message = f"{name} is {status} in {market}"
            if status == "restricted" and max_val is not None and amount is not None:
                if amount > max_val:
                    message = f"{name} at {amount}% exceeds {market} limit of {max_val}%"
                else:
                    message = f"{name} within {market} limit ({max_val}%)"
            findings.append(
                ComplianceFinding(
                    ingredient=ing.raw_name,
                    normalized_name=ing_norm,
                    market=market,
                    status=status,
                    max_percent=max_val,
                    source_ref=rule.get("source_ref", ""),
                    message=message,
                )
            )

        for rule in json_rules:
            market = (rule.get("market") or "").upper()
            if market not in markets_upper:
                continue
            name = rule.get("ingredient", "")
            aliases = rule.get("aliases", [])
            if not _ingredient_matches(ing_norm, ing_raw, name, aliases):
                continue
            status = (rule.get("status") or "").lower()
            findings.append(
                ComplianceFinding(
                    ingredient=ing.raw_name,
                    normalized_name=ing_norm,
                    market=market,
                    status=status,
                    max_percent=None,
                    source_ref=rule.get("source_ref", ""),
                    message=f"{name} is {status} in {market}",
                )
            )

    overall: ComplianceStatus = "pass"
    for f in findings:
        if f.status == "prohibited":
            overall = "fail"
            break
        if f.status == "restricted":
            if f.max_percent is not None and record.ingredients:
                for ing in record.ingredients:
                    if ing.raw_name == f.ingredient and ing.unit == "%" and ing.amount is not None:
                        if ing.amount > f.max_percent:
                            overall = "fail"
                            break
            if overall != "fail" and overall == "pass":
                overall = "warn"

    return ComplianceReport(status=overall, markets=markets_upper, findings=findings)
