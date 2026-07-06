"""Parser unit tests for Volume-8 column layouts."""
from app.formulation.parsers import parse_formula_block
from app.formulation.parsers.validate import filter_ingredient_lines
from app.formulation.schemas import IngredientLine


PRE_BLENDED_BLOCK = """
Shampoo
Starting formulation for a baby shampoo from a pre-blended concentrate.

wt%
35.00
64.90
0.10
q.s.
q.s.

Ingredients:
Sulfochem SBS
Water, soft
Fragrance
NaCl
Preservatives

Blending Procedure:
Charge mixing vessel with water and Sulfochem SBS.
"""


def test_pre_blended_concentrate_five_ingredients():
    ingredients, method, confidence = parse_formula_block(PRE_BLENDED_BLOCK)
    assert len(ingredients) == 5
    assert method in ("column_wt", "inline_wt")
    assert confidence >= 0.85
    names = {i.raw_name for i in ingredients}
    assert "Fragrance" in names
    assert "Sulfochem SBS" in names


def test_fragrance_not_filtered_as_junk():
    line = IngredientLine(
        raw_name="Fragrance",
        normalized_name="fragrance",
        amount=0.1,
        unit="wt%",
    )
    filtered = filter_ingredient_lines([line])
    assert len(filtered) == 1
