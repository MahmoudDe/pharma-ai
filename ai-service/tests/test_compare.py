from __future__ import annotations

from app.formulation.compare import compare_formulations
from app.formulation.schemas import FormulationRecord, IngredientLine


def _record(fid: str, name: str, ingredients: list[tuple[str, str, float]]) -> FormulationRecord:
    return FormulationRecord(
        id=fid,
        name=name,
        doc_id="doc",
        pdf_page=1,
        source_text=name,
        ingredients=[
            IngredientLine(raw_name=raw, normalized_name=norm, amount=amt, unit="%")
            for raw, norm, amt in ingredients
        ],
    )


def test_compare_cost_and_unique_ingredients():
    left = _record(
        "a",
        "Cheap",
        [("Water", "water", 95.0), ("Glycerin", "glycerin", 5.0)],
    )
    right = _record(
        "b",
        "Rich",
        [("Water", "water", 50.0), ("Tocopherol", "tocopherol", 50.0)],
    )
    report = compare_formulations(left, right)
    assert report.left_cost_per_kg is not None
    assert report.right_cost_per_kg is not None
    assert report.cost_delta_per_kg is not None
    assert report.right_cost_per_kg > report.left_cost_per_kg
    assert any("tocopherol" in x.lower() for x in report.only_in_right)


def test_compare_role_summaries():
    left = _record(
        "a",
        "Shampoo A",
        [("SLS", "sodium lauryl sulfate", 10.0), ("Glycerin", "glycerin", 5.0)],
    )
    right = _record(
        "b",
        "Shampoo B",
        [("CAPB", "cocamidopropyl betaine", 10.0), ("Glycerin", "glycerin", 5.0)],
    )
    report = compare_formulations(left, right)
    roles = {r.role for r in report.role_summaries}
    assert "surfactant" in roles
    assert report.summary_lines
