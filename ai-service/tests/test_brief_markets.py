from __future__ import annotations

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.reasoning.brief import apply_brief_filters
from app.schemas import StructuredBrief


def _record(name: str, ingredients: list[tuple[str, str]]) -> FormulationRecord:
    return FormulationRecord(
        id="f1",
        name=name,
        doc_id="doc",
        pdf_page=1,
        source_text="",
        ingredients=[
            IngredientLine(
                raw_name=raw,
                normalized_name=norm,
                amount=1.0,
                unit="%",
            )
            for raw, norm in ingredients
        ],
    )


def test_apply_brief_filters_excludes_eu_prohibited():
    clean = _record("Mild shampoo", [("Water", "water"), ("CAPB", "cocamidopropyl betaine")])
    banned = _record("Bad", [("Formaldehyde", "formaldehyde"), ("Water", "water")])
    brief = StructuredBrief(markets=["EU"])
    out = apply_brief_filters([clean, banned], brief)
    assert len(out) == 1
    assert out[0].name == "Mild shampoo"
