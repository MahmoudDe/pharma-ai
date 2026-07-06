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
