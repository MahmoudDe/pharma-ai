from app.formulation.parsers import parse_formula_block
from app.formulation.parsers.ocr_amounts import normalize_ocr_amount_line
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


OCR_FACIAL_BLOCK = """
Facial Cleanser
Wt%
1 6 . 4
0.1
12.5
5 . 0
4.0
1.0
1.0
Ingredients:
Water
Disodium EDTA
Polargel NF (Bentonite)
Monafax MAP 230
Propylene Glycol
"""


MOISTURISING_BLOCK = """
Moisturisins Anti-Acne Cream
Wt%
10.00
8 . 0 0
4.00
3.00
1.00
1.50
Inqredient:
Mineral oil (25 cS at 2 5 C )
Polawax GP200 (Nonionic emulsifying wax)
GMS A/S (Glyceryl stearate (and) PEG-100)
Crodamol IPM (Isopropyl Myristate)
Silicone 200/100 (Dimethicone)
Parsol MCX (Octyl methoxycinnamate)
Water deionised
Croderol GA 7000 (glycerin)
Purasal S/PF 90
Purac PH 90
Tocopherol acetate
Perfume. Preservative, Colour
to 100
4.00
8-18
0 . 0 8 - 0 . 2 3
0.5
qs
"""


def test_pre_blended_concentrate_five_ingredients():
    ingredients, method, confidence = parse_formula_block(PRE_BLENDED_BLOCK)
    assert len(ingredients) == 5
    assert method in ("column_wt", "inline_wt", "phase_inline", "leading_amounts")
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


def test_ocr_amount_normalization():
    assert normalize_ocr_amount_line("1 6 . 4") == "16.4"
    assert normalize_ocr_amount_line("8 . 0 0") == "8.00"
    assert normalize_ocr_amount_line("0 . 0 8 - 0 . 2 3") == "0.08"


def test_ocr_facial_water_amount():
    ingredients, method, _ = parse_formula_block(OCR_FACIAL_BLOCK)
    assert method in ("column_wt", "phase_inline", "leading_amounts")
    water = next(i for i in ingredients if i.raw_name == "Water")
    assert water.amount == 16.4


def test_moisturising_cream_twelve_ingredients():
    ingredients, method, confidence = parse_formula_block(MOISTURISING_BLOCK)
    assert method in ("column_wt", "phase_inline", "leading_amounts")
    assert len(ingredients) >= 10
    assert confidence >= 0.85
    names = {i.raw_name for i in ingredients}
    assert "Water deionised" in names
    assert "Tocopherol acetate" in names


def test_procedure_line_not_ingredient():
    line = IngredientLine(
        raw_name="Melt A, mix in B and fill while hot.",
        normalized_name="melt a mix in b",
        amount=1.0,
        unit="wt%",
    )
    assert filter_ingredient_lines([line]) == []


ROLL_ON_BLOCK = """
Anti-PersDirant Roll-On
Slightly cloudy, high viscosity

wt%
2.00
52.00

puredients:
A: Wacker-Belsil DMC 6032
Water

B: Ethanol Alcohol (Cosmetic grade)
25.00

C : Locron L
Tylose H 4000 P
20.00
0.5-1.0

Pigments, fragrances
q . s .
"""


def test_roll_on_part_labeled_five_ingredients():
    ingredients, method, confidence = parse_formula_block(ROLL_ON_BLOCK)
    assert method in ("part_labeled", "phase_inline")
    assert len(ingredients) == 5
    assert confidence >= 0.9
    phases = {i.phase for i in ingredients}
    assert phases == {"A", "B", "C"}
    water = next(i for i in ingredients if i.raw_name == "Water")
    assert water.amount == 52.0
    assert water.phase == "A"


PROSE_FRAGMENT = """
Formulation AP10 illustrates a typical antiperspirant stick with
aluminum chlorohydrate at 25% and dimethicone at 2%.
"""


def test_prose_percent_table_not_formula():
    ingredients, method, confidence = parse_formula_block(PROSE_FRAGMENT)
    assert len(ingredients) == 0
    assert confidence == 0.0
