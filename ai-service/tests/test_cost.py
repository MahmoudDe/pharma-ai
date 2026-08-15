from __future__ import annotations

from app.formulation.cost import estimate_formulation_cost, load_price_table, merge_price_rows
from app.formulation.schemas import FormulationRecord, IngredientLine


def _record(ingredients: list[tuple[str, str, float]]) -> FormulationRecord:
    return FormulationRecord(
        id="f-cost",
        name="Test formula",
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


def test_load_price_table_has_common_ingredients():
    prices = load_price_table()
    assert prices.get("water") == 0.05
    assert prices.get("glycerin") == 1.2


def test_estimate_formulation_cost_simple_blend():
    record = _record(
        [
            ("Water", "water", 90.0),
            ("Glycerin", "glycerin", 10.0),
        ],
    )
    est = estimate_formulation_cost(record)
    assert est.cost_per_kg is not None
    assert abs(est.cost_per_kg - 0.165) < 0.001
    assert est.covered_percent == 1.0
    assert est.missing_ingredients == []


def test_estimate_formulation_cost_reports_missing_prices():
    record = _record(
        [
            ("Water", "water", 50.0),
            ("Mystery polymer XYZ", "mystery polymer xyz", 50.0),
        ],
    )
    est = estimate_formulation_cost(record)
    assert est.cost_per_kg is not None
    assert est.covered_percent == 0.5
    assert any("Mystery" in m for m in est.missing_ingredients)


def test_merge_price_rows_persists(tmp_path, monkeypatch):
    from app.formulation.cost import _DATA_PATH, reload_price_table

    original_path = _DATA_PATH
    csv_path = tmp_path / "prices.csv"
    monkeypatch.setattr("app.formulation.cost._DATA_PATH", csv_path)
    reload_price_table()
    count = merge_price_rows([("custom wax", 9.5)])
    assert count >= 1
    prices = load_price_table()
    assert prices.get("custom wax") == 9.5
    monkeypatch.setattr("app.formulation.cost._DATA_PATH", original_path)
    reload_price_table()
