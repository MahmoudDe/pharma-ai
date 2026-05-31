"""Detect formula section blocks — delegates to unified segmentation."""
from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.metadata import infer_product_types
from app.ingestion.segments import segment_page
from app.ingestion.extract import PageRecord


@dataclass(slots=True)
class FormulaSection:
    name: str
    text: str
    product_types: list[str]


def detect_formula_sections(page_text: str) -> list[FormulaSection]:
    """Legacy API: segment a page string without full PageRecord context."""
    page = PageRecord(
        doc_id="_inline",
        doc_title="",
        pdf_page=0,
        printed_page=None,
        text=page_text,
    )
    segments = segment_page(page)
    return [
        FormulaSection(
            name=a.formula_name,
            text=a.raw_text,
            product_types=a.product_types or infer_product_types(a.raw_text, a.formula_name),
        )
        for a in segments.formulas
    ]
