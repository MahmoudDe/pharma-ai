from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import yaml

from app.kbs.config import DATA_DIR
from app.kbs.facts import FactContext, is_percent_unit
from app.kbs.rules.fidelity import amount_near_name
from app.kbs.schemas import RuleFinding


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CategoryRange:
    name: str
    typical_min: float
    typical_max: float
    hard_max: float
    ingredients: list[str]


@lru_cache
def load_ranges() -> list[CategoryRange]:
    path = DATA_DIR / "ingredient_ranges.yaml"
    if not path.is_file():
        logger.warning("KBS range knowledge file missing: %s", path)
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        logger.warning("Invalid YAML in %s; range rules disabled", path)
        return []
    categories: list[CategoryRange] = []
    for entry in data.get("categories", []):
        try:
            typical = entry.get("typical", [None, None])
            categories.append(
                CategoryRange(
                    name=str(entry["name"]),
                    typical_min=float(typical[0]),
                    typical_max=float(typical[1]),
                    hard_max=float(entry["hard_max"]),
                    ingredients=[str(i).strip().lower() for i in entry.get("ingredients", [])],
                )
            )
        except (KeyError, TypeError, ValueError, IndexError):
            logger.warning("Skipping malformed range category: %r", entry)
    return categories


def clear_ranges_cache() -> None:
    load_ranges.cache_clear()


def _match_category(normalized: str, raw: str) -> CategoryRange | None:
    normalized = normalized.strip().lower()
    raw = raw.strip().lower()
    best: CategoryRange | None = None
    best_len = 0
    for category in load_ranges():
        for candidate in category.ingredients:
            if not candidate:
                continue
            exact = candidate in (normalized, raw)
            contained = (
                f" {candidate} " in f" {normalized} " or f" {candidate} " in f" {raw} "
            )
            if (exact or contained) and len(candidate) > best_len:
                best = category
                best_len = len(candidate)
    return best


class IngredientRangeRule:
    rule_id = "ranges.ingredient-range"
    family = "ranges"

    def check(self, facts: FactContext) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for ing in facts.dosed_ingredients():
            if ing.amount is None:
                continue
            percentish = is_percent_unit(ing.unit) or (ing.unit is None and facts.percent_mode)
            if not percentish:
                continue
            category = _match_category(ing.normalized_name or "", ing.raw_name)
            if category is None:
                continue
            label = ing.raw_name.strip() or (ing.normalized_name or "")
            if ing.amount > category.hard_max:
                # If the value is printed right next to the name in the source,
                # the extraction is faithful — the formulation is just unusual
                # (e.g. anhydrous products). Only untraceable values gate.
                as_printed = amount_near_name(ing.raw_name, ing.amount, facts.combined_source)
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="warning" if as_printed else "error",
                        message=(
                            f"'{label}' at {ing.amount}% exceeds the plausible maximum "
                            f"of {category.hard_max}% for {category.name}"
                            + (" (value matches the source text)" if as_printed else "")
                        ),
                        ingredient=label,
                        field="amount",
                        observed=f"{ing.amount}%",
                        expected=f"<= {category.hard_max}% ({category.name})",
                    )
                )
            elif not (category.typical_min <= ing.amount <= category.typical_max):
                findings.append(
                    RuleFinding(
                        rule_id=self.rule_id,
                        family=self.family,
                        severity="warning",
                        message=(
                            f"'{label}' at {ing.amount}% is outside the typical "
                            f"{category.typical_min}–{category.typical_max}% range for {category.name}"
                        ),
                        ingredient=label,
                        field="amount",
                        observed=f"{ing.amount}%",
                        expected=(
                            f"{category.typical_min}–{category.typical_max}% ({category.name})"
                        ),
                    )
                )
        return findings


def build_rules() -> list:
    return [IngredientRangeRule()]
