"""Registry of active KBS rules."""
from __future__ import annotations

from app.kbs.rules import completeness, consistency, fidelity, name_quality, ranges
from app.kbs.rules.base import Rule


def get_rules() -> list[Rule]:
    return [
        *completeness.build_rules(),
        *consistency.build_rules(),
        *ranges.build_rules(),
        *fidelity.build_rules(),
        *name_quality.build_rules(),
    ]


def describe_rules() -> list[dict]:
    described = [
        {
            "rule_id": rule.rule_id,
            "family": rule.family,
            "description": (type(rule).__doc__ or "").strip().split("\n")[0],
            "source": "built-in",
        }
        for rule in get_rules()
    ]
    for category in ranges.load_ranges():
        described.append(
            {
                "rule_id": f"ranges.category.{category.name}",
                "family": "ranges",
                "description": (
                    f"{category.name}: typical {category.typical_min}–{category.typical_max}%, "
                    f"hard max {category.hard_max}% "
                    f"({len(category.ingredients)} known ingredients)"
                ),
                "source": "data/kbs/ingredient_ranges.yaml",
            }
        )
    return described
