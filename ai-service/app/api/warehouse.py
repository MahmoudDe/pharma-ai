"""Warehouse inventory upload, alias resolution, product discovery."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from app.config import get_settings
from app.warehouse import warehouse_store
from app.warehouse.alias_resolve import resolve_upload
from app.warehouse.match_products import discover_products
from app.warehouse.parse_upload import read_upload_bytes
from app.warehouse.schemas import (
    DiscoverRequest,
    DiscoverResponse,
    ResolveRequest,
    ResolveResponse,
    SetAliasRequest,
    UploadResponse,
    WarehouseMaterialRow,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.post("/upload", response_model=UploadResponse)
async def upload_inventory(file: UploadFile = File(...)) -> UploadResponse:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    data = await file.read()
    if len(data) > settings.warehouse_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB).")

    try:
        rows = read_upload_bytes(data, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(rows) > settings.warehouse_max_rows:
        raise HTTPException(
            status_code=400,
            detail=f"Too many rows (max {settings.warehouse_max_rows}).",
        )

    upload_id = warehouse_store.replace_active_upload(file.filename, rows)
    preview = [
        {"raw_name": r[0], "sku": r[1], "qty": r[2]}
        for r in rows[:10]
    ]
    return UploadResponse(
        upload_id=upload_id,
        filename=file.filename,
        row_count=len(rows),
        preview=preview,
    )


@router.post("/resolve", response_model=ResolveResponse)
def resolve_materials(body: ResolveRequest = Body(default_factory=ResolveRequest)) -> ResolveResponse:
    upload_id = body.upload_id
    try:
        return resolve_upload(upload_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Warehouse resolve failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _material_row(mat, settings) -> WarehouseMaterialRow:
    aliases = warehouse_store.get_aliases(mat.id)
    if aliases:
        a = aliases[0]
        return WarehouseMaterialRow(
            id=mat.id,
            raw_name=mat.raw_name,
            sku=mat.sku,
            qty=mat.qty,
            canonical_name=a.canonical_name,
            alias_source=a.source,  # type: ignore[arg-type]
            confidence=a.confidence,
            needs_review=a.confidence < settings.warehouse_review_threshold
            and a.source != "manual",
        )
    return WarehouseMaterialRow(
        id=mat.id,
        raw_name=mat.raw_name,
        sku=mat.sku,
        qty=mat.qty,
        needs_review=True,
    )


@router.patch("/materials/{material_id}", response_model=WarehouseMaterialRow)
def set_material_alias(material_id: int, body: SetAliasRequest) -> WarehouseMaterialRow:
    settings = get_settings()
    mat = warehouse_store.get_material(material_id)
    if mat is None:
        raise HTTPException(status_code=404, detail="Material not found.")
    canonical = body.canonical_name.strip()
    if not canonical:
        raise HTTPException(status_code=400, detail="canonical_name is required.")
    warehouse_store.save_alias(material_id, canonical, "manual", 1.0)
    warehouse_store.clear_discover_cache(mat.upload_id)
    updated = warehouse_store.get_material(material_id)
    assert updated is not None
    return _material_row(updated, settings)


@router.get("/materials")
def list_materials(upload_id: str | None = None) -> dict:
    settings = get_settings()
    uid = upload_id or warehouse_store.get_active_upload_id()
    if not uid:
        raise HTTPException(status_code=404, detail="No warehouse upload found.")

    rows = [_material_row(mat, settings) for mat in warehouse_store.list_materials(uid)]
    return {"upload_id": uid, "materials": [r.model_dump() for r in rows]}


@router.post("/discover", response_model=DiscoverResponse)
def discover(body: DiscoverRequest) -> DiscoverResponse:
    try:
        return discover_products(body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Warehouse discover failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/discover/{upload_id}", response_model=DiscoverResponse)
def discover_cached(upload_id: str, min_coverage: float = 50.0) -> DiscoverResponse:
    cached = warehouse_store.get_discover_cache(upload_id)
    if cached:
        return DiscoverResponse(
            upload_id=cached["upload_id"],
            material_count=cached["material_count"],
            products=cached["products"],
        )
    return discover(DiscoverRequest(upload_id=upload_id, min_coverage=min_coverage))
