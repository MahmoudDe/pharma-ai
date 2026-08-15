from __future__ import annotations

from unittest.mock import patch

from app.formulation.review import list_review_queue
from app.formulation.schemas import FormulationRecord, IngredientLine


def _record(id: str, confidence: float) -> FormulationRecord:
    return FormulationRecord(
        id=id,
        name=f"Formula {id}",
        doc_id="doc",
        pdf_page=1,
        source_text="water 90%",
        confidence=confidence,
        ingredients=[
            IngredientLine(raw_name="Water", normalized_name="water", amount=90.0, unit="%"),
        ],
    )


def test_list_review_queue_low_confidence():
    records = [_record("low1", 0.4), _record("ok1", 0.95)]
    with patch("app.formulation.review.list_reports_by_status", return_value=[]):
        with patch("app.formulation.review.list_formulations", return_value=records):
            with patch("app.formulation.review.get_verdicts", return_value={}):
                items = list_review_queue(confidence_max=0.75, limit=10)
    assert any(i.formulation_id == "low1" for i in items)
    assert not any(i.formulation_id == "ok1" for i in items)
