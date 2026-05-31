"""Warehouse parsing and coverage scoring tests."""
from __future__ import annotations

import io

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.warehouse.match_products import _ingredient_matches, _score_formulation
from app.warehouse.parse_upload import parse_inventory_file


def test_parse_csv_detects_material_column():
    csv = "material,sku,qty\nWater,W1,100\nGlycerin,W2,50\n"
    rows = parse_inventory_file(io.BytesIO(csv.encode()), "inventory.csv")
    assert len(rows) == 2
    assert rows[0][0] == "Water"
    assert rows[1][0] == "Glycerin"


def test_ingredient_matches_canonical_inventory():
    inv = {"water", "glycerin", "sodium laureth sulfate"}
    assert _ingredient_matches(inv, "Purified Water", "water")
    assert not _ingredient_matches(inv, "Carbomer", "carbomer")


def test_score_formulation_coverage_excludes_water():
    record = FormulationRecord(
        id="test-1",
        name="Test Shampoo",
        product_types=["shampoo"],
        doc_id="doc",
        pdf_page=1,
        source_text="sample",
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water"),
            IngredientLine(raw_name="Glycerin", normalized_name="glycerin"),
            IngredientLine(raw_name="SLS", normalized_name="sodium laureth sulfate"),
        ],
    )
    inv = {"water", "glycerin"}
    pct, _, missing = _score_formulation(record, inv, exclude_water=True)
    assert pct == 50.0
    assert "SLS" in missing[0] or any("sls" in m.lower() for m in missing)
