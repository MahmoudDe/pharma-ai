"""Completeness rules: is anything missing from the record?"""
from __future__ import annotations

import re

from app.kbs.config import get_kbs_config
from app.kbs.facts import FactContext
from app.kbs.schemas import RuleFinding


class HasNameRule:
    rule_id = "completeness.has-name"
    family = "completeness"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        name = facts.record.name.strip()
        if name and len(name) >= 3:
            return []
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="warning",
                message="Formulation has no usable name",
                field="name",
                observed=repr(facts.record.name),
            )
        ]


class MinIngredientsRule:
    rule_id = "completeness.min-ingredients"
    family = "completeness"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        minimum = int(get_kbs_config()["completeness"]["min_ingredients"])
        count = len(facts.record.ingredients)
        if count >= minimum:
            return []
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="error",
                message=f"Only {count} ingredient(s); a formulation needs at least {minimum}",
                field="ingredients",
                observed=str(count),
                expected=f">= {minimum}",
            )
        ]


class HasSourceTextRule:
    rule_id = "completeness.has-source-text"
    family = "completeness"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        if facts.combined_source.strip():
            return []
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="error",
                message="No source text stored; extraction cannot be traced to the document",
                field="source_text",
            )
        ]


class IngredientFieldsRule:
    """Each dosed ingredient needs a name, an amount and a unit."""

    rule_id = "completeness.ingredient-fields"
    family = "completeness"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for ing in facts.dosed_ingredients():
            label = ing.raw_name.strip() or "<unnamed>"
            if not ing.raw_name.strip():
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="error",
                        message="Ingredient line has no name",
                        field="raw_name",
                    )
                )
            if ing.amount is None:
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="warning",
                        message=f"'{label}' has no amount",
                        ingredient=label,
                        field="amount",
                    )
                )
            elif ing.unit is None and not facts.percent_mode:
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="warning",
                        message=f"'{label}' has an amount but no unit",
                        ingredient=label,
                        field="unit",
                    )
                )
        return findings


class MissedAmountsRule:
    """Many missing amounts while the source is full of numbers = lost data.

    A record where several dosed ingredients carry no amount is only a mild
    problem when the source genuinely lists none — but when the source text
    contains at least as many decimal amounts as there are gaps, extraction
    demonstrably dropped them, which is a precision error.
    """

    rule_id = "completeness.missed-amounts"
    family = "completeness"

    _DECIMAL_RE = re.compile(r"\b\d+\.\d{1,3}\b")

    def check(self, facts: FactContext) -> list[RuleFinding]:
        dosed = facts.dosed_ingredients()
        missing = [i for i in dosed if i.amount is None]
        if len(missing) < 3:
            return []
        decimals_in_source = len(self._DECIMAL_RE.findall(facts.combined_source))
        if decimals_in_source < len(missing):
            return []
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="error",
                message=(
                    f"{len(missing)} of {len(dosed)} dosed ingredients have no amount "
                    f"although the source text contains {decimals_in_source} numeric "
                    "values — extraction likely dropped the amounts"
                ),
                field="ingredients",
                observed=f"{len(missing)} missing",
            )
        ]


class NoAmountsRule:
    """A record with several ingredients and no amounts at all is not a
    verifiable formula — 'verified' must never be a vacuous claim.

    Complements MissedAmountsRule: fires only when the numeric-evidence
    condition of that rule does not (so exactly one of the two reports).
    """

    rule_id = "completeness.no-amounts"
    family = "completeness"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        dosed = facts.dosed_ingredients()
        if len(dosed) < 3:
            return []
        missing = [i for i in dosed if i.amount is None]
        if len(missing) != len(dosed):
            return []
        decimals = len(MissedAmountsRule._DECIMAL_RE.findall(facts.combined_source))
        if len(missing) >= 3 and decimals >= len(missing):
            return []  # MissedAmountsRule already reports this
        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity="error",
                message=(
                    f"None of the {len(dosed)} ingredients carries an amount — "
                    "the record cannot be verified as a precise formula"
                ),
                field="ingredients",
            )
        ]


class JunkRowRule:
    """Obvious non-ingredient rows (footers, references) parsed as ingredients."""

    rule_id = "completeness.junk-row"
    family = "completeness"

    _JUNK_RE = re.compile(r"^(?:SOURCE\s*:|Formula\s+Ref|Procedure\b|Blending\b|NOTE\s*:)", re.I)

    def check(self, facts: FactContext) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for ing in facts.record.ingredients:
            if self._JUNK_RE.match(ing.raw_name.strip()):
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="error",
                        message=f"Non-ingredient row parsed as ingredient: '{ing.raw_name.strip()[:60]}'",
                        ingredient=ing.raw_name.strip()[:60],
                        field="raw_name",
                    )
                )
        return findings


def build_rules() -> list:
    return [
        HasNameRule(),
        MinIngredientsRule(),
        HasSourceTextRule(),
        IngredientFieldsRule(),
        MissedAmountsRule(),
        NoAmountsRule(),
        JunkRowRule(),
    ]
