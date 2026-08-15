from __future__ import annotations

from app.reasoning.brief import format_structured_brief
from app.schemas import StructuredBrief


def test_format_structured_brief_includes_batch_and_cost():
    brief = StructuredBrief(
        product_type="shampoo",
        cost_target=12.0,
        batch_size=5.0,
        markets=["EU"],
    )
    text = format_structured_brief(brief)
    assert "target_batch_kg=5.0" in text
    assert "max_cost_usd_per_kg=12.0" in text
    assert "markets=EU" in text


def test_format_structured_brief_empty():
    assert format_structured_brief(None) == ""
    assert format_structured_brief(StructuredBrief()) == ""
