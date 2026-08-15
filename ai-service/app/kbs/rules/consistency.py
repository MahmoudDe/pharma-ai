from __future__ import annotations

from collections import Counter

from app.kbs.config import get_kbs_config
from app.kbs.facts import FactContext, is_percent_unit
from app.kbs.schemas import RuleFinding


class PercentSumRule:
    """In percent mode, dosed amounts (+ any q.s. remainder) must reach ~100."""

    rule_id = "consistency.percent-sum"
    family = "consistency"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        if not facts.percent_mode:
            return []
        cfg = get_kbs_config()["consistency"]
        amounts = [i.amount for i in facts.dosed_ingredients() if i.amount is not None]
        if len(amounts) < 2:
            return []
        total = sum(amounts)
        target = float(cfg["sum_target"])
        warn_tol = float(cfg["sum_warn_tolerance"])
        error_tol = float(cfg["sum_error_tolerance"])
        has_qs = bool(facts.qs_ingredients())

        if has_qs:
            # q.s. line fills up to 100 — the dosed part only must stay below it.
            if total <= target + warn_tol:
                return []
            severity = "error" if total > target + error_tol else "warning"
            message = (
                f"Dosed ingredients sum to {total:.2f}% but a q.s. line "
                f"should fill the remainder to {target:.0f}%"
            )
        else:
            deviation = abs(total - target)
            if deviation <= warn_tol:
                return []
            severity = "error" if deviation > error_tol else "warning"
            message = f"Ingredient percentages sum to {total:.2f}%, expected ~{target:.0f}%"

        return [
            RuleFinding(
                rule_id=self.rule_id,
                family=self.family,
                severity=severity,
                message=message,
                field="ingredients",
                observed=f"{total:.2f}",
                expected=f"~{target:.0f}",
            )
        ]


class AmountRangeRule:
    """Percent amounts must lie in (0, 100]."""

    rule_id = "consistency.amount-range"
    family = "consistency"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for ing in facts.dosed_ingredients():
            if ing.amount is None:
                continue
            label = ing.raw_name.strip() or "<unnamed>"
            percentish = is_percent_unit(ing.unit) or (ing.unit is None and facts.percent_mode)
            if ing.amount <= 0:
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="error",
                        message=f"'{label}' has a non-positive amount ({ing.amount})",
                        ingredient=label,
                        field="amount",
                        observed=str(ing.amount),
                        expected="> 0",
                    )
                )
            elif percentish and ing.amount > 100:
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="error",
                        message=f"'{label}' is {ing.amount}% — a percentage cannot exceed 100",
                        ingredient=label,
                        field="amount",
                        observed=str(ing.amount),
                        expected="<= 100",
                    )
                )
        return findings


class DuplicateIngredientRule:
    rule_id = "consistency.duplicate-ingredient"
    family = "consistency"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        names = [
            (i.normalized_name or i.raw_name).strip().lower()
            for i in facts.record.ingredients
            if (i.normalized_name or i.raw_name).strip()
        ]
        findings: list[RuleFinding] = []
        for name, count in Counter(names).items():
            if count > 1 and name != "water":
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="warning",
                        message=f"Ingredient '{name}' appears {count} times",
                        ingredient=name,
                        observed=str(count),
                        expected="1",
                    )
                )
        return findings


class UnitCoherenceRule:
    """Mixing percent-like units with mass/volume units in one formula is suspect."""

    rule_id = "consistency.unit-coherence"
    family = "consistency"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        units = [i.unit.strip().lower() for i in facts.dosed_ingredients() if i.unit]
        if not units:
            return []
        percent_units = {u for u in units if is_percent_unit(u)}
        other_units = {u for u in units if not is_percent_unit(u)}
        if percent_units and other_units:
            return [
                RuleFinding(
                    rule_id=self.rule_id,
                    family=self.family,
                    severity="warning",
                    message=(
                        "Mixed unit systems in one formulation: "
                        f"{sorted(percent_units)} vs {sorted(other_units)}"
                    ),
                    field="unit",
                    observed=", ".join(sorted(percent_units | other_units)),
                )
            ]
        return []


def build_rules() -> list:
    return [
        PercentSumRule(),
        AmountRangeRule(),
        DuplicateIngredientRule(),
        UnitCoherenceRule(),
    ]
