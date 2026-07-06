"""Tests for Phase 4 ingestion parsers."""
from app.formulation.parsers import parse_formula_block
from app.formulation.parsers.japan_prescription import parse_japan_prescription
from app.formulation.parsers.phase_inline_wt import parse_phase_inline_wt
from app.formulation.parsers.reference_filter import is_reference_table_block

ANTIPERSPIRANT_STICK = """
Antiperspirant Stick
Firm stick with soft rub

Inqredients:
Wt8
A Wacker-Belsil SDM 6022/Stearoxy Dimethicone,
Dimethicone
6.00
Ado1 66/Isostearyl Alcohol
13.50
Brij 70/Steareth-20
2.50
Lanette O/Cetearyl Alcohol
20.00

B Wacker HDK H 15/Silica Dimethyl Silylate
Locron P/Aluminum Chlorhydrate
1.00
25.00

C Wacker-Belsil DM 100/Dimethicone
Wacker-Belsil CM 040/Cyclomethicone
2.00
30.00

Fragrances, pigments
q.s.
"""

JAPAN_TOILET_SOAP = """
Prescription 5.1  Toilet soap (mold drying)
Part
Ingredient
% (100 g)
1
A
Coconut acid (nv255)
20.00
2
A
Tallow fatty acid or palm oil fatty acid (nv198)
80.00
3
A
Glycerin
6.00
4
C
EDTA-2Na
0.20
5
C
Sodium citrate
0.50
6
B
Sodium hydroxide
17.57
B
Purified water
44.00
Directions
1) Weigh 1–3, and heat to 80°C.
"""

FATTY_ACID_TABLE = """
[TABLE]
Unsaponified | matter | content(%) | 48
Iodine | number | – 73 89
Acid | value Saponification | ratioa value
"""


def test_phase_inline_antiperspirant_stick():
    lines = parse_phase_inline_wt(ANTIPERSPIRANT_STICK)
    assert len(lines) >= 8
    names = {i.raw_name for i in lines}
    assert any("Lanette" in n for n in names)
    assert any("Locron" in n for n in names)


def test_japan_prescription_toilet_soap():
    lines = parse_japan_prescription(JAPAN_TOILET_SOAP)
    assert len(lines) >= 6
    names = {i.normalized_name or i.raw_name for i in lines}
    assert any("coconut" in n for n in names)
    assert any("glycerin" in n for n in names)


def test_reference_table_rejected():
    assert is_reference_table_block(FATTY_ACID_TABLE)
    ings, method, _ = parse_formula_block(FATTY_ACID_TABLE)
    assert len(ings) == 0


def test_japan_prescription_requires_ingredient_table():
    stub = "Prescription 5.2 ). Some prose about liquid soaps."
    assert parse_japan_prescription(stub) == []

ROLL_ON_R1 = """
Anti-PersDirant Roll-On
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
"""

ROLL_ON_R2 = """
Antiuersuirant Roll-On
Wt%
70.00
5.00
Inqredients:
A Wacker-Belsil CM 040/Cyclomethicone
Wacker-Belsil DM 100/Dimethicone
B Tegin M/Glyceryl Stearate
2.70
C Locron P/Aluminum chlorhydrate
Wacker HDK H 15/Silica Dimethyl Silylate
20.00
1.00
"""

ROLL_ON_MATERIALS = """
Antiperspirant Suspension Roll-on
Materials:- -
Cyclomethicone (SF1173)
Wt%
45.7
Cyclomethicone (SF1202)
19.5
Quaternium-18 Hectorite
2.5
Ethanol
2.0
Aluminum Zirconium Tetrachlorohydrex Gly (ZAG)
25.0
Silica
0.3
"""


def test_roll_on_colon_parts_and_leading_amounts():
    lines = parse_phase_inline_wt(ROLL_ON_R1)
    assert len(lines) >= 5
    amounts = {i.raw_name: i.amount for i in lines}
    assert amounts.get("Water") == 52.0
    assert amounts.get("Ethanol Alcohol (Cosmetic grade)") == 25.0


def test_roll_on_part_a_two_names():
    lines = parse_phase_inline_wt(ROLL_ON_R2)
    assert len(lines) >= 5
    names = {i.raw_name for i in lines}
    assert any("Wacker-Belsil CM" in n for n in names)
    assert any("Locron" in n for n in names)


def test_roll_on_materials_interleaved():
    lines = parse_phase_inline_wt(ROLL_ON_MATERIALS)
    assert len(lines) >= 6
    names = {i.raw_name for i in lines}
    assert any("SF1173" in n for n in names)
    assert any("SF1202" in n for n in names)


def test_antiperspirant_via_parse_formula_block():
    ings, method, conf = parse_formula_block(ANTIPERSPIRANT_STICK)
    assert method == "phase_inline"
    assert len(ings) >= 8
    assert conf >= 0.85


# --- OCR repair regressions (patterns observed in the real corpus) ---------

PIPE_TABLE_ROLL_ON = """
Clear Antiperspirant Roll-On

[TABLE]
puredients: | wt%
A: Wacker-Belsil DMC 6032 | 2 00
.
Water | 52 00
.
B: Ethanol Alcohol (Cosmeticgrade) | 25 00
.
C: Locron L | 20 00
.
Tylose H 4000 P | 0 .5-1 .0
Pigments, fragrances | q s
. .
[/TABLE]
"""

SPACED_DECIMAL_LOTION = """
Moisture Lotion
Ingredients:
Wt%
Propylene Glycol USP
5 . 0 0
Superhartolan
2 . 0 0
Glycerin
3.00
Water
89.00
Preservative
1.00
"""


def test_pipe_table_amounts_parsed():
    ings, method, _conf = parse_formula_block(PIPE_TABLE_ROLL_ON)
    amounts = {i.raw_name: i.amount for i in ings}
    assert amounts.get("Wacker-Belsil DMC 6032") == 2.0
    assert amounts.get("Water") == 52.0
    assert amounts.get("Ethanol Alcohol (Cosmeticgrade)") == 25.0
    assert amounts.get("Locron L") == 20.0
    assert amounts.get("Tylose H 4000 P") == 0.5
    # prose/junk rows must not become ingredients
    assert not any("Temperature" in n or "[TABLE]" in n for n in amounts)
    # no ingredient keeps the pipe or the raw OCR cell in its name
    assert not any("|" in n for n in amounts)


def test_pipe_table_phases_assigned():
    ings, _method, _conf = parse_formula_block(PIPE_TABLE_ROLL_ON)
    phases = {i.raw_name: i.phase for i in ings}
    assert phases.get("Wacker-Belsil DMC 6032") == "A"
    assert phases.get("Ethanol Alcohol (Cosmeticgrade)") == "B"
    assert phases.get("Locron L") == "C"


def test_spaced_decimals_repaired():
    ings, _method, _conf = parse_formula_block(SPACED_DECIMAL_LOTION)
    amounts = {i.raw_name: i.amount for i in ings}
    assert amounts.get("Propylene Glycol USP") == 5.0
    assert amounts.get("Superhartolan") == 2.0
    # nothing may parse to a bogus zero amount
    assert all(a is None or a > 0 for a in amounts.values())


def test_normalize_table_cell_amount():
    from app.formulation.parsers.ocr_amounts import normalize_table_cell_amount

    assert normalize_table_cell_amount("52 00") == "52.00"
    assert normalize_table_cell_amount("2 00") == "2.00"
    assert normalize_table_cell_amount("0 .5-1 .0") == "0.5-1.0"
    assert normalize_table_cell_amount("q s") == "q.s."
    assert normalize_table_cell_amount("12.5") == "12.5"
    assert normalize_table_cell_amount("") == ""
    assert normalize_table_cell_amount("wt%") == ""


def test_repair_spaced_decimals_is_conservative():
    from app.formulation.parsers.ocr_amounts import repair_spaced_decimals

    assert repair_spaced_decimals("5 . 0 0") == "5.00"
    assert repair_spaced_decimals("1 6 . 4") == "16.4"  # numeric-only line collapses
    # normal prose with sentence dots is left alone
    text = "Mix at 45C. Stir for 10 minutes. pH 5.5"
    assert repair_spaced_decimals(text) == text
    # a name line followed by numbers on other lines is untouched
    assert repair_spaced_decimals("Glycerin\n3.00") == "Glycerin\n3.00"


def test_repair_three_fragment_decimal():
    from app.formulation.parsers.ocr_amounts import repair_spaced_decimals

    assert repair_spaced_decimals("2 . 0 0 0") == "2.000"
    assert repair_spaced_decimals("74.28 4") == "74.284"
    # two separate amounts on one line must not be merged
    assert repair_spaced_decimals("25.0 45.7") == "25.0 45.7"


NUMBERED_STAGE_LOTION = """
Moisture Lotion
Staqe: Material:
wt%

Oil Phase:

1
Light Mineral Oil
7.000
2
Superhartolan
2 . 0 0 0
3
AEC Dimethicone VlOO
1.200
4
Amerchol LlOl
3.000
5
Stearic Acid-Triple Pressed
5.000

Aqueous Phase:

6
Water; Pure
74.284
7
Glycerine BP
3.000
8
Carbopol 934
0.166
9
Triethanolamine 99%
2.500
10
Add preservative(s) & colour to suit
0.500

Cooling Cycle:

11
Fragrance
0.350

Mixing Instructions:

This is an oil-in-water emulsion.
Heat the Oil Phase to 70/75C and mix well.
"""


def test_numbered_stage_table_parsed():
    ings, method, conf = parse_formula_block(NUMBERED_STAGE_LOTION)
    assert method == "numbered_stage"
    amounts = {i.raw_name: i.amount for i in ings}
    # "99%" is a concentration grade in the name, NOT the amount
    assert amounts.get("Triethanolamine 99%") == 2.5
    assert amounts.get("Superhartolan") == 2.0  # spaced decimal repaired
    assert amounts.get("Water; Pure") == 74.284
    total = sum(a for a in amounts.values() if a)
    assert 97.0 <= total <= 103.0  # the true sum is ~99%
    assert conf >= 0.85


def test_numbered_stage_phases():
    ings, _method, _conf = parse_formula_block(NUMBERED_STAGE_LOTION)
    phases = {i.raw_name: i.phase for i in ings}
    assert phases.get("Light Mineral Oil") == "Oil"
    assert phases.get("Glycerine BP") == "Aqueous"
    assert phases.get("Fragrance") == "Cooling"


PHASE_COLUMN_SOAP = """
d-Limonene Hand Soap
Starting formulation for a hand soap containing d-Limonene
as a grease cutter.

Wt%

Inuredients:
Phase A:
Water, DI
Carbopol 1382
Triethanolamine 99%

7 3 . 4 0
1.00
1.50

Phase B:
Sulfochem ES-2
Amidex 0
Neodol 91-8

5.10
2.00
2.00

Phase C:
d-Limonene

15.00

Blending Procedure:
Disperse the Carbopol in water.
"""


def test_phase_column_block_parsed():
    ings, method, _conf = parse_formula_block(PHASE_COLUMN_SOAP)
    assert method == "phase_column"
    amounts = {i.raw_name: i.amount for i in ings}
    assert amounts.get("Water, DI") == 73.4  # OCR-spaced "7 3 . 4 0" repaired
    assert amounts.get("Carbopol 1382") == 1.0
    assert amounts.get("Triethanolamine 99%") == 1.5  # grade kept in name
    assert amounts.get("d-Limonene") == 15.0
    total = sum(a for a in amounts.values() if a)
    assert 97.0 <= total <= 103.0
    phases = {i.raw_name: i.phase for i in ings}
    assert phases.get("Sulfochem ES-2") == "B"


COMPONENT_HAIR_MILK = """
Sprayable Hair Milk

Component:
wt%
Dehyquart L 80/Dicocoylethyl Hydroxyethylmonium Metho-
sulfate (and) Propylene Glycol
2.0
Lamesoft PO 65/Coco-Glucoside (and) Glyceryl Oleate
2.0
Cetiol HE/PEG-7 Glyceryl Cocoate
1.0
Water
ad 100
Preservatives
q . s .

pH Value: 3.5

Mix the ingredients at room temperature.
"""

LEADING_AMOUNTS_BUBBLE_BATH = """
Bubble Bath
Starting formulation for an economical pearly bubble bath.

Wt%
25.00
73.65
0.25
typical: 0.80
typical: 0.05

Inqredients;
Sulfochem B-2090P
Water, soft
Fragrance
NaCl
Citric acid
Preservatives
Hydrolyzed milk protein

0.25
q.s.

Blending Procedure:
With medium agitation, mix water and milk protein in main vessel.
"""

JAPAN_TO_100 = """
Prescription 5.30 Simple shampoo
Part
Ingredient
% (100 g)
1
A
Sodium laureth sulfate
15.00
2
A
Cocamidopropyl betaine
5.00
3
B
Citric acid
0.30
Purified water
to 100
Directions
1) Mix everything.
"""


def test_component_wt_trade_codes_not_amounts():
    ings, method, _conf = parse_formula_block(COMPONENT_HAIR_MILK)
    assert method == "component_wt"
    amounts = {i.raw_name: i.amount for i in ings}
    # "L 80" and "PO 65" are trade codes and must stay in the name
    dehyquart = next(n for n in amounts if n.startswith("Dehyquart"))
    assert "80" in dehyquart and amounts[dehyquart] == 2.0
    lamesoft = next(n for n in amounts if n.startswith("Lamesoft"))
    assert "65" in lamesoft and amounts[lamesoft] == 2.0
    # water "ad 100" is a q.s. fill, not 100%
    water = next(i for i in ings if i.raw_name == "Water")
    assert water.amount is None and water.unit == "qs"


def test_leading_amounts_bubble_bath():
    ings, method, _conf = parse_formula_block(LEADING_AMOUNTS_BUBBLE_BATH)
    assert method == "leading_amounts"
    amounts = {i.raw_name: i.amount for i in ings}
    assert amounts.get("Sulfochem B-2090P") == 25.0
    assert amounts.get("Water, soft") == 73.65
    assert amounts.get("NaCl") == 0.8  # "typical: 0.80"
    # trailing amounts pair in column order: 0.25 then q.s.
    assert amounts.get("Preservatives") == 0.25
    milk = next(i for i in ings if i.raw_name == "Hydrolyzed milk protein")
    assert milk.amount is None and milk.unit == "qs"
    total = sum(a for a in amounts.values() if a)
    assert 97.0 <= total <= 103.0


def test_japan_to_100_water_is_qs():
    ings, method, _conf = parse_formula_block(JAPAN_TO_100)
    assert method == "japan_rx"
    water = next(i for i in ings if "water" in i.raw_name.lower())
    assert water.amount is None and water.unit == "qs"
