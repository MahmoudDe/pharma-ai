"""Pydantic models for structured formulations."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ExtractionMethod = Literal[
    "regex",
    "table",
    "wtg",
    "column_wt",
    "inline_wt",
    "part_function",
    "part_labeled",
    "phase_inline",
    "japan_rx",
    "list",
    "llm",
]


class IngredientLine(BaseModel):
    raw_name: str
    normalized_name: str | None = None
    amount: float | None = None
    unit: str | None = None
    phase: str | None = None


class FormulationRecord(BaseModel):
    id: str
    name: str
    product_types: list[str] = Field(default_factory=list)
    doc_id: str
    doc_title: str = ""
    pdf_page: int
    printed_page: int | None = None
    source_text: str
    ingredients: list[IngredientLine] = Field(default_factory=list)
    procedure: list[str] = Field(default_factory=list)
    vector_text: str = ""
    extraction_method: ExtractionMethod = "regex"
    confidence: float = 0.5


class FormulationSearchRequest(BaseModel):
    ingredient: str | None = None
    product_type: str | None = None
    doc_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class StructuredFormulationSummary(BaseModel):
    formulation_id: str
    name: str
    product_types: list[str]
    doc_id: str
    pdf_page: int
    printed_page: int | None = None
    ingredient_count: int
    confidence: float
    precision_score: float | None = None
    kbs_status: str | None = None
