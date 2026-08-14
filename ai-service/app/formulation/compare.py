"""Structured formula comparison: cost, compliance, and ingredient roles."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.formulation.cost import estimate_formulation_cost
from app.formulation.regulatory import check_formulation
from app.formulation.schemas import FormulationRecord, IngredientLine
from app.formulation.normalize import normalize_ingredient_name


_ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("surfactant", re.compile(r"sulfate|betaine|capb|lauryl|laureth|surfactant", re.I)),
    ("emulsifier", re.compile(r"emulsif|stearate|peg-|cetearyl|polysorbate", re.I)),
    ("preservative", re.compile(r"phenoxy|paraben|benzoate|sorbate|caprylyl|preserv", re.I)),
    ("humectant", re.compile(r"glycerin|propylene glycol|sorbitol|humectant", re.I)),
    ("oil", re.compile(r"\boil\b|butter|wax|dimethicone|silicone", re.I)),
]


@dataclass(slots=True)
class IngredientDelta:
    key: str
    raw_name: str
    left_amount: float | None
    left_unit: str | None
    right_amount: float | None
    right_unit: str | None


@dataclass(slots=True)
class RoleSummary:
    role: str
    left_count: int
    right_count: int
    left_examples: list[str] = field(default_factory=list)
    right_examples: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FormulationCompareReport:
    left_id: str
    right_id: str
    left_name: str
    right_name: str
    left_cost_per_kg: float | None
    right_cost_per_kg: float | None
    cost_delta_per_kg: float | None
    left_compliance: str
    right_compliance: str
    markets: list[str]
    only_in_left: list[str]
    only_in_right: list[str]
    ingredient_deltas: list[IngredientDelta]
    role_summaries: list[RoleSummary]
    summary_lines: list[str]


def _ingredient_key(ing: IngredientLine) -> str:
    norm = ing.normalized_name or normalize_ingredient_name(ing.raw_name) or ing.raw_name
    return norm.lower().strip()


def _infer_roles(ingredients: list[IngredientLine]) -> dict[str, list[str]]:
    roles: dict[str, list[str]] = {}
    for ing in ingredients:
        text = f"{ing.raw_name} {ing.normalized_name or ''}"
        for role, pattern in _ROLE_PATTERNS:
            if pattern.search(text):
                roles.setdefault(role, []).append(ing.raw_name)
    return roles


def compare_formulations(
    left: FormulationRecord,
    right: FormulationRecord,
    markets: list[str] | None = None,
) -> FormulationCompareReport:
    markets = [m.strip().upper() for m in (markets or []) if m and m.strip()]

    left_cost = estimate_formulation_cost(left).cost_per_kg
    right_cost = estimate_formulation_cost(right).cost_per_kg
    cost_delta = None
    if left_cost is not None and right_cost is not None:
        cost_delta = round(right_cost - left_cost, 4)

    left_comp = check_formulation(left, markets).status if markets else "skipped"
    right_comp = check_formulation(right, markets).status if markets else "skipped"

    map_l = {_ingredient_key(i): i for i in left.ingredients}
    map_r = {_ingredient_key(i): i for i in right.ingredients}
    keys_l = set(map_l.keys())
    keys_r = set(map_r.keys())

    only_left = [map_l[k].raw_name for k in sorted(keys_l - keys_r)]
    only_right = [map_r[k].raw_name for k in sorted(keys_r - keys_l)]

    deltas: list[IngredientDelta] = []
    for key in sorted(keys_l & keys_r):
        a, b = map_l[key], map_r[key]
        if a.amount == b.amount and a.unit == b.unit:
            continue
        deltas.append(
            IngredientDelta(
                key=key,
                raw_name=a.raw_name,
                left_amount=a.amount,
                left_unit=a.unit,
                right_amount=b.amount,
                right_unit=b.unit,
            )
        )

    roles_l = _infer_roles(left.ingredients)
    roles_r = _infer_roles(right.ingredients)
    role_summaries: list[RoleSummary] = []
    for role in sorted(set(roles_l) | set(roles_r)):
        role_summaries.append(
            RoleSummary(
                role=role,
                left_count=len(roles_l.get(role, [])),
                right_count=len(roles_r.get(role, [])),
                left_examples=roles_l.get(role, [])[:4],
                right_examples=roles_r.get(role, [])[:4],
            )
        )

    summary: list[str] = []
    if cost_delta is not None:
        if cost_delta > 0:
            summary.append(f"Right formula costs ${cost_delta:.2f}/kg more than left.")
        elif cost_delta < 0:
            summary.append(f"Right formula costs ${abs(cost_delta):.2f}/kg less than left.")
        else:
            summary.append("Estimated raw material cost is the same.")
    if markets:
        summary.append(f"Compliance ({', '.join(markets)}): left={left_comp}, right={right_comp}.")
    if only_left:
        summary.append(f"{len(only_left)} ingredient(s) only in left formula.")
    if only_right:
        summary.append(f"{len(only_right)} ingredient(s) only in right formula.")
    if deltas:
        summary.append(f"{len(deltas)} shared ingredient(s) with different amounts.")

    return FormulationCompareReport(
        left_id=left.id,
        right_id=right.id,
        left_name=left.name,
        right_name=right.name,
        left_cost_per_kg=left_cost,
        right_cost_per_kg=right_cost,
        cost_delta_per_kg=cost_delta,
        left_compliance=left_comp,
        right_compliance=right_comp,
        markets=markets,
        only_in_left=only_left,
        only_in_right=only_right,
        ingredient_deltas=deltas,
        role_summaries=role_summaries,
        summary_lines=summary,
    )
