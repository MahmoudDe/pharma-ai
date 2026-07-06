"""Completeness rules: is anything missing from the record?"""
from __future__ import annotations

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


def build_rules() -> list:
    return [
        HasNameRule(),
        MinIngredientsRule(),
        HasSourceTextRule(),
        IngredientFieldsRule(),
    ]
