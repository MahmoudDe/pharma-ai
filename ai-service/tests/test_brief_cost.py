from __future__ import annotations

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.reasoning.brief import apply_brief_filters, exceeds_cost_target
from app.schemas import StructuredBrief


def _record(name: str, ingredients: list[tuple[str, str, float]]) -> FormulationRecord:
    return FormulationRecord(
        id="f1",
        name=name,
        doc_id="doc",
        pdf_page=1,
        source_text="",
        ingredients=[
            IngredientLine(
                raw_name=raw,
                normalized_name=norm,
                amount=amt,
                unit="%",
            )
            for raw, norm, amt in ingredients
        ],
    )


def test_exceeds_cost_target_when_above_threshold():
    cheap = _record(
        "Cheap",
        [("Water", "water", 95.0), ("Glycerin", "glycerin", 5.0)],
    )
    expensive = _record(
        "Rich",
        [("Water", "water", 50.0), ("Tocopherol", "tocopherol", 50.0)],
    )
    brief = StructuredBrief(cost_target=1.0)
    assert not exceeds_cost_target(cheap, brief)
    assert exceeds_cost_target(expensive, brief)


def test_apply_brief_filters_excludes_over_budget():
    cheap = _record(
        "Cheap",
        [("Water", "water", 95.0), ("Glycerin", "glycerin", 5.0)],
    )
    expensive = _record(
        "Rich",
        [("Water", "water", 50.0), ("Tocopherol", "tocopherol", 50.0)],
    )
    brief = StructuredBrief(cost_target=1.0)
    out = apply_brief_filters([cheap, expensive], brief)
    assert len(out) == 1
    assert out[0].name == "Cheap"
