"""Tests for the individual KBS rule families."""
from __future__ import annotations

import pytest

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.kbs.facts import build_facts, is_qs_line
from app.kbs.rules.completeness import build_rules as completeness_rules
from app.kbs.rules.consistency import build_rules as consistency_rules
from app.kbs.rules.fidelity import AmountVerbatimRule, NameInSourceRule, amount_in_source
from app.kbs.rules.ranges import IngredientRangeRule


GOOD_SOURCE = """BABY SHAMPOO
Water 74.50
Sodium Laureth Sulfate 12.0
Cocamidopropyl Betaine 8.0
Glycerin 3.0
PEG-80 Sorbitan Laurate 2.0
Phenoxyethanol 0.40
Citric Acid 0.10
Mix surfactants into water, adjust pH to 5.5.
"""


def make_record(**kwargs) -> FormulationRecord:
    defaults = dict(
        id="f1",
        name="Baby Shampoo",
        product_types=["baby", "shampoo"],
        doc_id="doc1",
        pdf_page=10,
        source_text=GOOD_SOURCE,
        extraction_method="table",
        confidence=0.8,
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=74.5, unit="%"),
            IngredientLine(
                raw_name="Sodium Laureth Sulfate",
                normalized_name="sodium laureth sulfate",
                amount=12.0,
                unit="%",
            ),
            IngredientLine(
                raw_name="Cocamidopropyl Betaine",
                normalized_name="cocamidopropyl betaine",
                amount=8.0,
                unit="%",
            ),
            IngredientLine(raw_name="Glycerin", normalized_name="glycerin", amount=3.0, unit="%"),
            IngredientLine(
                raw_name="PEG-80 Sorbitan Laurate",
                normalized_name="peg-80 sorbitan laurate",
                amount=2.0,
                unit="%",
            ),
            IngredientLine(
                raw_name="Phenoxyethanol",
                normalized_name="phenoxyethanol",
                amount=0.4,
                unit="%",
            ),
            IngredientLine(
                raw_name="Citric Acid", normalized_name="citric acid", amount=0.1, unit="%"
            ),
        ],
    )
    defaults.update(kwargs)
    return FormulationRecord(**defaults)


def run_family(rules, record) -> list:
    facts = build_facts(record)
    findings = []
    for rule in rules:
        findings.extend(rule.check(facts))
    return findings


# ---------------------------------------------------------------- completeness

def test_clean_record_has_no_completeness_findings():
    assert run_family(completeness_rules(), make_record()) == []


def test_missing_amount_flagged():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=90.0, unit="%"),
            IngredientLine(raw_name="Carbomer", amount=None, unit=None),
        ]
    )
    findings = run_family(completeness_rules(), record)
    assert any(
        f.rule_id == "completeness.ingredient-fields" and f.field == "amount" for f in findings
    )


def test_too_few_ingredients_is_error():
    record = make_record(ingredients=[IngredientLine(raw_name="Water", amount=100.0, unit="%")])
    findings = run_family(completeness_rules(), record)
    errors = [f for f in findings if f.rule_id == "completeness.min-ingredients"]
    assert len(errors) == 1 and errors[0].severity == "error"


def test_missing_source_text_is_error():
    record = make_record(source_text="", vector_text="")
    findings = run_family(completeness_rules(), record)
    assert any(f.rule_id == "completeness.has-source-text" for f in findings)


def test_qs_line_not_penalized_for_missing_amount():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water q.s. to 100", amount=None, unit=None),
            IngredientLine(raw_name="Glycerin", amount=5.0, unit="%"),
            IngredientLine(raw_name="Phenoxyethanol", amount=0.4, unit="%"),
        ]
    )
    assert is_qs_line(record.ingredients[0])
    findings = run_family(completeness_rules(), record)
    assert not any(f.field == "amount" for f in findings)


# ---------------------------------------------------------------- consistency

def test_clean_record_has_no_consistency_findings():
    findings = run_family(consistency_rules(), make_record())
    assert findings == []


def test_sum_far_from_100_is_error():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=100.0, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=37.2, unit="%"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    sums = [f for f in findings if f.rule_id == "consistency.percent-sum"]
    assert len(sums) == 1 and sums[0].severity == "error"


def test_sum_slightly_off_is_warning():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=90.0, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=5.0, unit="%"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    sums = [f for f in findings if f.rule_id == "consistency.percent-sum"]
    assert len(sums) == 1 and sums[0].severity == "warning"


def test_qs_line_satisfies_sum_check():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water q.s. to 100", amount=None, unit=None),
            IngredientLine(raw_name="SLES", amount=12.0, unit="%"),
            IngredientLine(raw_name="CAPB", amount=8.0, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=3.0, unit="%"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    assert not any(f.rule_id == "consistency.percent-sum" for f in findings)


def test_percentage_over_100_is_error():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=250.0, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=5.0, unit="%"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    assert any(
        f.rule_id == "consistency.amount-range" and f.severity == "error" for f in findings
    )


def test_negative_amount_is_error():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=95.0, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=-2.0, unit="%"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    assert any(
        f.rule_id == "consistency.amount-range" and f.severity == "error" for f in findings
    )


def test_duplicate_ingredient_is_warning():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Glycerin", normalized_name="glycerin", amount=3.0, unit="%"),
            IngredientLine(raw_name="Glycerine", normalized_name="glycerin", amount=2.0, unit="%"),
            IngredientLine(raw_name="Water", normalized_name="water", amount=95.0, unit="%"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    assert any(f.rule_id == "consistency.duplicate-ingredient" for f in findings)


def test_mixed_units_is_warning():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=80.0, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=20.0, unit="mg"),
        ]
    )
    findings = run_family(consistency_rules(), record)
    assert any(f.rule_id == "consistency.unit-coherence" for f in findings)


# ---------------------------------------------------------------- domain ranges

def test_range_rule_passes_clean_record():
    assert run_family([IngredientRangeRule()], make_record()) == []


def test_preservative_over_hard_max_is_error_when_untraceable():
    # 8% is implausible for a preservative AND nowhere near the name in the
    # source -> extraction artifact -> error
    record = make_record(
        source_text="CREAM BASE\nWater 92.00\nPhenoxyethanol 0.40\nMix well.",
        vector_text="",
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=92.0, unit="%"),
            IngredientLine(
                raw_name="Phenoxyethanol",
                normalized_name="phenoxyethanol",
                amount=8.0,
                unit="%",
            ),
        ],
    )
    findings = run_family([IngredientRangeRule()], record)
    hits = [f for f in findings if f.ingredient == "Phenoxyethanol"]
    assert len(hits) == 1 and hits[0].severity == "error"


def test_implausible_value_printed_in_source_is_warning():
    # the same implausible value printed right next to the name -> the
    # extraction is faithful, the formulation is just unusual -> warning
    record = make_record(
        source_text="CREAM BASE\nWater 92.00\nPhenoxyethanol 8.0\nMix well.",
        vector_text="",
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=92.0, unit="%"),
            IngredientLine(
                raw_name="Phenoxyethanol",
                normalized_name="phenoxyethanol",
                amount=8.0,
                unit="%",
            ),
        ],
    )
    findings = run_family([IngredientRangeRule()], record)
    hits = [f for f in findings if f.ingredient == "Phenoxyethanol"]
    assert len(hits) == 1 and hits[0].severity == "warning"


def test_preservative_above_typical_is_warning():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=93.0, unit="%"),
            IngredientLine(
                raw_name="Phenoxyethanol",
                normalized_name="phenoxyethanol",
                amount=1.5,
                unit="%",
            ),
        ]
    )
    findings = run_family([IngredientRangeRule()], record)
    hits = [f for f in findings if f.ingredient == "Phenoxyethanol"]
    assert len(hits) == 1 and hits[0].severity == "warning"


def test_unknown_ingredient_not_range_checked():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=50.0, unit="%"),
            IngredientLine(raw_name="Unobtainium X", amount=50.0, unit="%"),
        ]
    )
    findings = run_family([IngredientRangeRule()], record)
    assert not any(f.ingredient == "Unobtainium X" for f in findings)


# ---------------------------------------------------------------- source fidelity

def test_fidelity_passes_when_amounts_verbatim():
    findings = run_family([AmountVerbatimRule(), NameInSourceRule()], make_record())
    assert findings == []


@pytest.mark.parametrize(
    ("amount", "source", "expected"),
    [
        (2.5, "Glycerin 2.50 wtg", True),
        (2.5, "Glycerin 2.5", True),
        (12.0, "SLES 12.0", True),
        (12.0, "SLES 12", True),
        (0.4, "Preservative 0.40", True),
        (3.0, "totally different 7.2 numbers 41", False),
        (2.5, "value is 12.5 here", False),  # must not match inside another number
    ],
)
def test_amount_in_source_matching(amount, source, expected):
    assert amount_in_source(amount, source) is expected


def test_unverified_amount_is_warning_for_table_extraction():
    record = make_record(
        extraction_method="table",
        ingredients=[
            IngredientLine(raw_name="Water", amount=74.5, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=19.37, unit="%"),
        ],
    )
    findings = run_family([AmountVerbatimRule()], record)
    hits = [f for f in findings if f.ingredient == "Glycerin"]
    assert len(hits) == 1 and hits[0].severity == "warning"


def test_unverified_amount_is_error_for_llm_extraction():
    record = make_record(
        extraction_method="llm",
        ingredients=[
            IngredientLine(raw_name="Water", amount=74.5, unit="%"),
            IngredientLine(raw_name="Glycerin", amount=19.37, unit="%"),
        ],
    )
    findings = run_family([AmountVerbatimRule()], record)
    hits = [f for f in findings if f.ingredient == "Glycerin"]
    assert len(hits) == 1 and hits[0].severity == "error"


def test_name_missing_from_source_is_warning():
    record = make_record(
        ingredients=[
            IngredientLine(raw_name="Water", amount=74.5, unit="%"),
            IngredientLine(raw_name="Hyaluronic Acid", amount=12.0, unit="%"),
        ]
    )
    findings = run_family([NameInSourceRule()], record)
    assert any(f.ingredient == "Hyaluronic Acid" for f in findings)
