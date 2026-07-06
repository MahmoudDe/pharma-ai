"""Tests for the KBS engine, scoring, report store and service orchestration."""
from __future__ import annotations

import pytest

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.kbs import report_store
from app.kbs.config import get_kbs_config
from app.kbs.engine import run_rules, score_findings, status_for_score
from app.kbs.facts import build_facts
from app.kbs.registry import describe_rules, get_rules
from app.kbs.schemas import RuleFinding
from app.kbs.service import validate_and_rescore, validate_record

from tests.test_kbs_rules import GOOD_SOURCE, make_record


@pytest.fixture()
def kbs_db(tmp_path, monkeypatch):
    db_path = tmp_path / "kbs_reports.db"
    monkeypatch.setattr("app.kbs.report_store.DB_PATH", db_path)
    return db_path


# ---------------------------------------------------------------- engine

def test_engine_runs_all_registered_rules():
    facts = build_facts(make_record())
    findings, executed = run_rules(facts, get_rules())
    assert executed == len(get_rules())
    assert findings == []


def test_engine_survives_a_broken_rule():
    class BrokenRule:
        rule_id = "test.broken"
        family = "consistency"

        def check(self, facts):
            raise RuntimeError("boom")

    class OkRule:
        rule_id = "test.ok"
        family = "consistency"

        def check(self, facts):
            return [
                RuleFinding(
                    rule_id=self.rule_id,
                    family=self.family,
                    severity="info",
                    message="fine",
                )
            ]

    facts = build_facts(make_record())
    findings, executed = run_rules(facts, [BrokenRule(), OkRule()])
    assert executed == 1
    assert [f.rule_id for f in findings] == ["test.ok"]


# ---------------------------------------------------------------- scoring

def test_config_weights_sum_to_one():
    weights = get_kbs_config()["weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_perfect_record_scores_one():
    score, family_scores = score_findings([])
    assert score == 1.0
    assert all(fs.score == 1.0 for fs in family_scores)


def test_errors_penalize_more_than_warnings():
    warning = [
        RuleFinding(rule_id="x", family="fidelity", severity="warning", message="w")
    ]
    error = [RuleFinding(rule_id="x", family="fidelity", severity="error", message="e")]
    warn_score, _ = score_findings(warning)
    error_score, _ = score_findings(error)
    assert error_score < warn_score < 1.0


def test_status_bands():
    assert status_for_score(0.39) == "low_precision"
    assert status_for_score(0.4) == "review"
    assert status_for_score(0.69) == "review"
    assert status_for_score(0.7) == "verified"
    assert status_for_score(1.0) == "verified"


def test_any_precision_error_blocks_verified():
    error = [RuleFinding(rule_id="x", family="consistency", severity="error", message="e")]
    assert status_for_score(0.95, error) == "review"
    warning_only = [
        RuleFinding(rule_id="x", family="consistency", severity="warning", message="w")
    ]
    assert status_for_score(0.95, warning_only) == "verified"
    regulatory_error = [
        RuleFinding(rule_id="x", family="regulatory", severity="error", message="banned")
    ]
    # compliance is reported separately and must not mask precision
    assert status_for_score(0.95, regulatory_error) == "verified"


def test_record_with_bad_sum_is_never_verified(kbs_db):
    record = make_record(
        id="sum217",
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
            # duplicated block inflating the sum well past 100%
            IngredientLine(raw_name="Water", normalized_name="water", amount=74.5, unit="%"),
            IngredientLine(
                raw_name="Sodium Laureth Sulfate",
                normalized_name="sles",
                amount=12.0,
                unit="%",
            ),
            IngredientLine(
                raw_name="Cocamidopropyl Betaine",
                normalized_name="capb",
                amount=8.0,
                unit="%",
            ),
            IngredientLine(raw_name="Glycerin", normalized_name="glycerine", amount=3.0, unit="%"),
        ],
    )
    report = validate_record(record, markets=[], persist=False)
    assert report.status != "verified"
    assert any(f.rule_id == "consistency.percent-sum" for f in report.errors())


# ---------------------------------------------------------------- service

def test_validate_clean_record_is_verified(kbs_db):
    report = validate_record(make_record(), markets=[], persist=True)
    assert report.status == "verified"
    assert report.precision_score == 1.0
    assert report.errors() == []
    assert report.rules_run == len(get_rules())
    # persisted and readable back
    stored = report_store.get_report("f1")
    assert stored is not None
    assert stored.precision_score == 1.0


def test_validate_garbage_record_is_flagged(kbs_db):
    record = make_record(
        id="f2",
        name="",
        extraction_method="llm",
        source_text="This page discusses packaging materials and nothing else.",
        vector_text="",
        ingredients=[
            IngredientLine(raw_name="Mercury Extract", amount=250.0, unit="%"),
            IngredientLine(raw_name="Mystery Compound", amount=-5.0, unit="%"),
            IngredientLine(raw_name="Phantom Oil", amount=310.0, unit="%"),
        ],
    )
    report = validate_record(record, markets=[], persist=False)
    assert report.status == "low_precision"
    assert report.precision_score < 0.4
    assert len(report.errors()) >= 4  # amounts out of range + unverified in source


def test_verified_beats_review_beats_low_precision(kbs_db):
    clean = validate_record(make_record(id="a"), markets=[], persist=False)
    slightly_off = validate_record(
        make_record(
            id="b",
            ingredients=[
                IngredientLine(raw_name="Water", normalized_name="water", amount=74.5, unit="%"),
                IngredientLine(raw_name="Glycerin", normalized_name="glycerin", amount=19.4, unit="%"),
            ],
        ),
        markets=[],
        persist=False,
    )
    garbage = validate_record(
        make_record(
            id="c",
            name="",
            extraction_method="llm",
            source_text="unrelated text",
            vector_text="",
            ingredients=[
                IngredientLine(raw_name="X", amount=999.0, unit="%"),
                IngredientLine(raw_name="Y", amount=-1.0, unit="%"),
                IngredientLine(raw_name="Z", amount=500.0, unit="%"),
            ],
        ),
        markets=[],
        persist=False,
    )
    assert clean.precision_score > slightly_off.precision_score > garbage.precision_score


def test_regulatory_findings_do_not_change_precision_score(kbs_db):
    source = "Cream base\nWater 99.90\nFormaldehyde 0.10\nMix well."
    record = make_record(
        id="f3",
        source_text=source,
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=99.9, unit="%"),
            IngredientLine(
                raw_name="Formaldehyde",
                normalized_name="formaldehyde",
                amount=0.1,
                unit="%",
            ),
        ],
    )
    with_reg = validate_record(record, markets=["EU"], persist=False)
    without_reg = validate_record(record, markets=[], persist=False)
    assert with_reg.precision_score == without_reg.precision_score
    assert with_reg.compliance_status == "fail"
    assert without_reg.compliance_status == "skipped"
    assert any(f.family == "regulatory" for f in with_reg.findings)


def test_validate_and_rescore_updates_confidence(kbs_db, monkeypatch):
    upserts: list[FormulationRecord] = []

    class FakeStore:
        def upsert(self, record):
            upserts.append(record)

    monkeypatch.setattr("app.kbs.service.get_store", lambda: FakeStore())

    record = make_record(confidence=0.5)
    report = validate_and_rescore(record, markets=[])
    # clean record: precision 1.0 -> blended confidence 0.4*0.5 + 0.6*1.0 = 0.8
    assert report.rescored_confidence == pytest.approx(0.8)
    assert len(upserts) == 1
    assert upserts[0].confidence == pytest.approx(0.8)


# ---------------------------------------------------------------- report store

def test_report_store_roundtrip_and_verdicts(kbs_db):
    report = validate_record(make_record(id="r1"), markets=[], persist=True)
    validate_record(
        make_record(
            id="r2",
            name="",
            extraction_method="llm",
            source_text="nothing relevant",
            vector_text="",
            ingredients=[
                IngredientLine(raw_name="A", amount=400.0, unit="%"),
                IngredientLine(raw_name="B", amount=-3.0, unit="%"),
                IngredientLine(raw_name="C", amount=600.0, unit="%"),
            ],
        ),
        markets=[],
        persist=True,
    )
    assert report_store.count_reports() == 2
    verdicts = report_store.get_verdicts(["r1", "r2", "missing"])
    assert set(verdicts) == {"r1", "r2"}
    assert verdicts["r1"][1] == "verified"
    assert verdicts["r2"][1] == "low_precision"
    assert report_store.get_report("missing") is None
    assert report.validated_at  # timestamp recorded


# ---------------------------------------------------------------- registry

def test_registry_describes_builtin_and_yaml_rules():
    described = describe_rules()
    ids = [d["rule_id"] for d in described]
    assert "fidelity.amount-verbatim" in ids
    assert "consistency.percent-sum" in ids
    assert any(d["source"].endswith("ingredient_ranges.yaml") for d in described)


# ---------------------------------------------------------------- chunk fidelity

def test_chunk_drift_rule():
    from app.kbs.rules.fidelity import ChunkDriftRule

    record = make_record()
    # matching chunk -> no finding
    facts = build_facts(record, indexed_chunk_texts=[record.source_text])
    assert ChunkDriftRule().check(facts) == []
    # mismatched chunk -> drift warning
    facts = build_facts(record, indexed_chunk_texts=["Totally different indexed content."])
    findings = ChunkDriftRule().check(facts)
    assert len(findings) == 1 and findings[0].rule_id == "fidelity.chunk-drift"
    # vector store unavailable -> rule skips
    facts = build_facts(record, indexed_chunk_texts=None)
    assert ChunkDriftRule().check(facts) == []


def test_validate_survives_qdrant_down(kbs_db, monkeypatch):
    import app.kbs.chunks as kbs_chunks

    kbs_chunks.reset_availability()

    def boom(_ids):
        raise ConnectionError("qdrant down")

    monkeypatch.setattr(
        "app.ingestion.index.fetch_chunks_by_formulation_ids", boom, raising=True
    )
    report = validate_record(make_record(), markets=[], persist=False)
    assert report.status == "verified"  # validation unaffected
    # availability is cached off after the first failure
    assert kbs_chunks.fetch_indexed_chunk_texts("x") is None
    kbs_chunks.reset_availability()
