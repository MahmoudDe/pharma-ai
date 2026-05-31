"""Discover book formulas makeable from warehouse inventory."""
from __future__ import annotations

import re

from app.config import get_settings
from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import FormulationRecord
from app.formulation.store import list_formulations
from app.warehouse import warehouse_store
from app.warehouse.matching import expand_inventory, ingredient_in_inventory
from app.warehouse.schemas import (
    DiscoverProductResult,
    DiscoverRequest,
    DiscoverResponse,
    IngredientMatchDetail,
)


_WATER_RE = re.compile(
    r"^(water|aqua|purified water|deionized water|demineralized water)$",
    re.I,
)
_JUNK_NAME_RE = re.compile(
    r"^(wt\s*%|wt%|\d+\.?\d*\s*%|formulation\s*\d*|page\s*\d+|cosmetic and toiletry formulations\s*$)",
    re.I,
)


def _is_water(name: str) -> bool:
    return bool(_WATER_RE.match(name.strip()))


def _is_junk_formulation(record: FormulationRecord) -> bool:
    name = (record.name or "").strip()
    if len(name) < 5:
        return True
    if _JUNK_NAME_RE.match(name):
        return True
    if name.isdigit():
        return True
    return False


def _score_formulation(
    record: FormulationRecord,
    inventory: set[str],
    *,
    exclude_water: bool,
    fuzzy_threshold: int,
) -> tuple[float, list[IngredientMatchDetail], list[str], int]:
    matched_details: list[IngredientMatchDetail] = []
    missing: list[str] = []
    counted = 0
    matched_count = 0

    for ing in record.ingredients:
        raw = (ing.raw_name or "").strip()
        if not raw or len(raw) < 2:
            continue
        norm = ing.normalized_name or normalize_ingredient_name(raw)
        if exclude_water and _is_water(raw):
            continue
        counted += 1
        ok = ingredient_in_inventory(
            inventory,
            raw,
            norm,
            fuzzy_threshold=fuzzy_threshold,
        )
        matched_details.append(
            IngredientMatchDetail(
                raw_name=raw,
                canonical=norm,
                matched=ok,
            )
        )
        if ok:
            matched_count += 1
        else:
            missing.append(raw)

    if counted == 0:
        return 0.0, matched_details, missing, 0

    pct = 100.0 * matched_count / counted
    return pct, matched_details, missing, counted


def _tier(coverage: float, makeable: float, partial: float) -> str:
    if coverage >= makeable:
        return "makeable"
    if coverage >= partial:
        return "partial"
    return "low"


def discover_products(req: DiscoverRequest) -> DiscoverResponse:
    settings = get_settings()
    uid = req.upload_id or warehouse_store.get_active_upload_id()
    if not uid:
        raise ValueError("No warehouse upload found.")

    cache_key = f"{req.min_coverage}:{req.product_type or ''}:{req.exclude_water}"
    cached = warehouse_store.get_discover_cache(uid)
    if cached and cached.get("cache_key") == cache_key:
        return DiscoverResponse(
            upload_id=cached["upload_id"],
            material_count=cached["material_count"],
            products=cached["products"],
        )

    raw_inv = warehouse_store.get_canonical_inventory(uid)
    if not raw_inv:
        raise ValueError("Resolve materials before discovery.")

    inventory = expand_inventory(raw_inv)
    records = list_formulations(
        product_type=req.product_type,
        limit=800,
    )
    if not records:
        records = list_formulations(limit=800)

    makeable_threshold = settings.warehouse_makeable_coverage
    fuzzy_threshold = max(80, settings.warehouse_fuzzy_threshold - 2)
    products: list[DiscoverProductResult] = []

    for rec in records:
        if _is_junk_formulation(rec):
            continue
        if len(rec.ingredients) < 2:
            continue

        pct, matched_details, missing, counted = _score_formulation(
            rec,
            inventory,
            exclude_water=req.exclude_water,
            fuzzy_threshold=fuzzy_threshold,
        )
        if counted < 2:
            continue
        if pct < req.min_coverage:
            continue

        tier = _tier(pct, makeable_threshold, req.min_coverage)
        quote = (rec.source_text or rec.name)[:280].strip()
        products.append(
            DiscoverProductResult(
                formulation_id=rec.id,
                name=rec.name,
                product_types=rec.product_types,
                doc_id=rec.doc_id,
                pdf_page=rec.pdf_page,
                printed_page=rec.printed_page,
                coverage_pct=round(pct, 1),
                tier=tier,  # type: ignore[arg-type]
                matched_ingredients=matched_details,
                missing_ingredients=missing,
                citation_quote=quote,
            )
        )

    products.sort(
        key=lambda p: (
            0 if p.tier == "makeable" else 1 if p.tier == "partial" else 2,
            -p.coverage_pct,
            p.name.lower(),
        ),
    )

    response = DiscoverResponse(
        upload_id=uid,
        material_count=len(raw_inv),
        products=products[:100],
    )
    warehouse_store.cache_discover(
        uid,
        {
            **response.model_dump(),
            "cache_key": cache_key,
            "min_coverage": req.min_coverage,
        },
    )
    return response
