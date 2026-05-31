"""Discover book formulas makeable from warehouse inventory."""
from __future__ import annotations

import re

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.schemas import FormulationRecord
from app.formulation.store import list_formulations
from app.warehouse import warehouse_store
from app.warehouse.schemas import (
    DiscoverProductResult,
    DiscoverRequest,
    DiscoverResponse,
    IngredientMatchDetail,
)


_WATER_RE = re.compile(r"^(water|aqua|purified water|deionized water)$", re.I)


def _is_water(name: str) -> bool:
    return bool(_WATER_RE.match(name.strip()))


def _ingredient_matches(canonical_inv: set[str], raw: str, norm: str | None) -> bool:
    candidates = {raw.lower()}
    if norm:
        candidates.add(norm.lower())
    n = normalize_ingredient_name(raw)
    if n:
        candidates.add(n.lower())
    for c in candidates:
        if c in canonical_inv:
            return True
        for inv in canonical_inv:
            if c in inv or inv in c:
                return True
    return False


def _score_formulation(
    record: FormulationRecord,
    canonical_inv: set[str],
    *,
    exclude_water: bool,
) -> tuple[float, list[IngredientMatchDetail], list[str]]:
    matched_details: list[IngredientMatchDetail] = []
    missing: list[str] = []
    counted = 0
    matched_count = 0

    for ing in record.ingredients:
        raw = ing.raw_name or ""
        norm = ing.normalized_name or normalize_ingredient_name(raw)
        if exclude_water and _is_water(raw):
            continue
        counted += 1
        ok = _ingredient_matches(canonical_inv, raw, norm)
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
        return 0.0, matched_details, missing

    pct = 100.0 * matched_count / counted
    return pct, matched_details, missing


def _tier(coverage: float, makeable: float, partial: float) -> str:
    if coverage >= makeable:
        return "makeable"
    if coverage >= partial:
        return "partial"
    return "low"


def discover_products(req: DiscoverRequest) -> DiscoverResponse:
    uid = req.upload_id or warehouse_store.get_active_upload_id()
    if not uid:
        raise ValueError("No warehouse upload found.")

    cached = warehouse_store.get_discover_cache(uid)
    if cached and cached.get("min_coverage") == req.min_coverage:
        return DiscoverResponse(**cached)

    canonical_inv = warehouse_store.get_canonical_inventory(uid)
    if not canonical_inv:
        raise ValueError("Resolve materials before discovery.")

    records = list_formulations(
        product_type=req.product_type,
        limit=500,
    )
    if not records:
        records = list_formulations(limit=500)

    makeable_threshold = 95.0
    products: list[DiscoverProductResult] = []

    for rec in records:
        if len(rec.ingredients) < 2:
            continue
        pct, matched_details, missing = _score_formulation(
            rec,
            canonical_inv,
            exclude_water=req.exclude_water,
        )
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

    products.sort(key=lambda p: (-p.coverage_pct, p.name))

    response = DiscoverResponse(
        upload_id=uid,
        material_count=len(canonical_inv),
        products=products[:100],
    )
    warehouse_store.cache_discover(
        uid,
        {
            **response.model_dump(),
            "min_coverage": req.min_coverage,
        },
    )
    return response
