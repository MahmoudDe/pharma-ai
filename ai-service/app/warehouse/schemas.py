from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AliasSource = Literal["rules", "corpus", "llm", "manual", "arabic", "embedding", "override", "unresolved"]


class WarehouseMaterialRow(BaseModel):
    id: int
    raw_name: str
    sku: str | None = None
    qty: float | None = None
    canonical_name: str | None = None
    alias_source: AliasSource | None = None
    confidence: float = 0.0
    needs_review: bool = False


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    row_count: int
    preview: list[dict[str, str | float | None]]


class SetAliasRequest(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=200)


class ResolveRequest(BaseModel):
    upload_id: str | None = None


class ResolveResponse(BaseModel):
    upload_id: str
    resolved: int
    needs_review: int
    materials: list[WarehouseMaterialRow]


class DiscoverRequest(BaseModel):
    upload_id: str | None = None
    min_coverage: float = Field(default=50.0, ge=0, le=100)
    product_type: str | None = None
    exclude_water: bool = True
    banned_ingredients: list[str] | None = None
    markets: list[str] | None = None
    max_cost: float | None = Field(None, ge=0)


class IngredientMatchDetail(BaseModel):
    raw_name: str
    canonical: str | None = None
    matched: bool


class DiscoverProductResult(BaseModel):
    formulation_id: str
    name: str
    product_types: list[str]
    doc_id: str
    pdf_page: int
    printed_page: int | None = None
    coverage_pct: float
    tier: Literal["makeable", "partial", "low"]
    matched_ingredients: list[IngredientMatchDetail]
    missing_ingredients: list[str]
    citation_quote: str
    estimated_cost_per_kg: float | None = None


class DiscoverResponse(BaseModel):
    upload_id: str
    material_count: int
    products: list[DiscoverProductResult]
