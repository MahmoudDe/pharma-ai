from __future__ import annotations

from app.formulation.regulatory import check_formulation
from app.formulation.schemas import FormulationRecord, IngredientLine


def test_compliance_fail_prohibited():
    record = FormulationRecord(
        id="x",
        name="Test",
        doc_id="doc",
        pdf_page=1,
        source_text="",
        ingredients=[
            IngredientLine(raw_name="Formaldehyde", normalized_name="formaldehyde", amount=0.1, unit="%"),
            IngredientLine(raw_name="Water", normalized_name="water", amount=99.9, unit="%"),
        ],
    )
    report = check_formulation(record, ["EU"])
    assert report.status == "fail"
    assert any(f.status == "prohibited" for f in report.findings)


def test_compliance_pass_clean():
    record = FormulationRecord(
        id="x",
        name="Mild shampoo",
        doc_id="doc",
        pdf_page=1,
        source_text="",
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=90.0, unit="%"),
            IngredientLine(raw_name="CAPB", normalized_name="cocamidopropyl betaine", amount=10.0, unit="%"),
        ],
    )
    report = check_formulation(record, ["EU", "US"])
    assert report.status == "pass"
    assert len(report.findings) == 0
