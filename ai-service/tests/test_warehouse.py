from __future__ import annotations

import io

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.formulation.normalize import normalize_ingredient_name
from app.warehouse.match_products import _is_junk_formulation, _score_formulation
from app.warehouse.matching import expand_inventory, ingredient_in_inventory
from app.warehouse.parse_upload import parse_inventory_file


def test_parse_csv_detects_material_column():
    csv = "material,sku,qty\nWater,W1,100\nGlycerin,W2,50\n"
    rows = parse_inventory_file(io.BytesIO(csv.encode()), "inventory.csv")
    assert len(rows) == 2
    names = {r[0] for r in rows}
    assert names == {"Water", "Glycerin"}


def test_methocel_f4m_alias():
    assert normalize_ingredient_name("Methocel F4M") == "hydroxypropyl methylcellulose"


def test_ingredient_matches_canonical_inventory():
    inv = expand_inventory({"water", "glycerin", "sodium laureth sulfate"})
    assert ingredient_in_inventory(inv, "Purified Water", "water")
    assert not ingredient_in_inventory(inv, "Carbomer", "carbomer")


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
    inv = expand_inventory({"water", "glycerin"})
    pct, _, missing, counted = _score_formulation(
        record, inv, exclude_water=True, fuzzy_threshold=86
    )
    assert counted == 2
    assert pct == 50.0
    assert any("sls" in m.lower() for m in missing)


def test_junk_formulation_filtered():
    junk = FormulationRecord(
        id="j1",
        name="Wt%",
        product_types=[],
        doc_id="d",
        pdf_page=1,
        source_text="",
        ingredients=[
            IngredientLine(raw_name="Glycerin", normalized_name="glycerin"),
            IngredientLine(raw_name="Water", normalized_name="water"),
        ],
    )
    assert _is_junk_formulation(junk)
