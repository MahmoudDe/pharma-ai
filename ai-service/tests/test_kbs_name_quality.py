from __future__ import annotations

import pytest

from app.kbs.facts import build_facts
from app.kbs.rules.name_quality import GarbledNameRule, score_name

from tests.test_kbs_rules import make_record


def run_rule(name: str):
    record = make_record(name=name)
    return GarbledNameRule().check(build_facts(record))


@pytest.mark.parametrize(
    "name",
    [
        "Antidandruff ShamDoo",        # mid-word cap: Shampoo
        "Hiqh Meltinq Point Lipstick", # q-not-u: High Melting
        "HeDarin Cream",               # mid-word cap: Heparin
        "Anti-Aqina Cream",            # q-not-u: Anti-Aging
        "Wt$",                         # stray unit token
        "Mackstat SBC-8 (Mild Shampoo Blend) | 32 0",  # pipe + amount tail
        "Drv/Damaqed Hair Shampoo",    # vowelless 'Drv' + q-not-u
        "___",                         # mostly non-letters
        "0.55",                        # bare number
    ],
)
def test_garbled_names_flagged(name):
    findings = run_rule(name)
    assert len(findings) == 1
    assert findings[0].rule_id == "completeness.name-quality"
    assert findings[0].severity == "info"  # never touches the precision score


@pytest.mark.parametrize(
    "name",
    [
        "Baby Shampoo",
        "Sunscreen Cream W/O. fatty",
        "Mackadet BSC (Baby Shampoo Concentrate)",   # BSC is a legit acronym
        "Mackadet SBC-8 (Mild Shampoo Blend)",       # SBC acronym
        "PEG-80 Sorbitan Laurate",
        "This formulation utilizes Eastman AQ55S polymer to improve",  # AQ55S trade code
        "Prescription 5.47 Hair gel finisher (for dry and lustrous hair)",  # 'dry'
        "pH Balanced Cleanser",                       # 'pH' is not mid-word garble
    ],
)
def test_clean_names_not_flagged(name):
    assert run_rule(name) == []


def test_pipe_name_suggests_cleaned_title():
    findings = run_rule("Silk Skin Cream | 12 0")
    assert findings and findings[0].expected == "Silk Skin Cream"


def test_name_finding_does_not_change_precision_score():
    # a clean formula with a garbled title stays verified
    from app.kbs.engine import score_findings, status_for_score

    findings = run_rule("Antidandruff ShamDoo")
    score, _ = score_findings(findings)
    assert score == 1.0
    assert status_for_score(score, findings) == "verified"


def test_score_name_is_conservative_on_empty():
    assert score_name("")[0] == 0
