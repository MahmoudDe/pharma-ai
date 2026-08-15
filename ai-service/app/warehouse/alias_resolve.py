from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.formulation.normalize import normalize_ingredient_name
from app.warehouse.embedding_match import embedding_canonical
from app.warehouse.matching import canonical_key
from app.reasoning.llm import _client
from app.warehouse import warehouse_store
from app.warehouse.arabic_aliases import has_arabic, resolve_arabic_alias
from app.warehouse.corpus_index import corpus_ingredient_names
from app.warehouse.schemas import ResolveResponse, WarehouseMaterialRow


logger = logging.getLogger(__name__)


def _rules_canonical(raw: str) -> tuple[str, float] | None:
    if has_arabic(raw):
        return None
    norm = normalize_ingredient_name(raw)
    if not norm:
        return None
    return norm, 0.95


def _fuzzy_canonical(raw: str, threshold: int) -> tuple[str, float] | None:
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return None

    corpus = corpus_ingredient_names()
    if not corpus:
        return None
    choices = [c[1] for c in corpus]
    match = process.extractOne(
        normalize_ingredient_name(raw) or raw.lower(),
        choices,
        scorer=fuzz.token_sort_ratio,
    )
    if not match:
        return None
    norm, score, _ = match
    if score < threshold:
        return None
    return norm, min(0.92, score / 100.0)


def _llm_batch_resolve(names: list[str]) -> dict[str, tuple[str, float]]:
    settings = get_settings()
    if not settings.llm_api_key or not names:
        return {}

    client = _client()
    prompt = (
        "Map each warehouse/trade material name (Arabic transliteration or English) to the "
        "closest standard INCI / cosmetic ingredient name used in formulation books. "
        "Return JSON object "
        '{"mappings": [{"input": "...", "canonical": "...", "confidence": 0.0-1.0}]}'
        f" for: {json.dumps(names[: settings.warehouse_llm_batch_size], ensure_ascii=False)}"
    )
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You map Arabic transliterated trade names and English trade names "
                        "to standard INCI ingredient names in English."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        items = data.get("mappings") or data.get("results") or []
        out: dict[str, tuple[str, float]] = {}
        for item in items:
            inp = str(item.get("input", "")).strip()
            can = str(item.get("canonical", "")).strip()
            conf = float(item.get("confidence", 0.75))
            if inp and can:
                out[inp.lower()] = (can, conf)
        return out
    except Exception as exc:
        logger.warning("LLM alias batch failed: %s", exc)
        return {}


def _resolve_one_material(
    raw_name: str,
    fuzzy_threshold: int,
    embed_threshold: float,
) -> tuple[str, str, float] | None:
    """Return (canonical, source, confidence) or None if unresolved."""
    override = warehouse_store.get_alias_override(raw_name)
    if override:
        return canonical_key(override), "override", 1.0

    hit = None
    source = "rules"
    if has_arabic(raw_name):
        hit = resolve_arabic_alias(raw_name)
        source = "arabic"
    if not hit:
        hit = _rules_canonical(raw_name)
        source = "rules"
    if not hit:
        hit = _fuzzy_canonical(raw_name, fuzzy_threshold)
        source = "corpus"
    if not hit:
        hit = embedding_canonical(raw_name, threshold=embed_threshold)
        if hit:
            source = "embedding"
    if hit:
        return canonical_key(hit[0]), source, hit[1]
    return None


def resolve_upload(upload_id: str | None = None) -> ResolveResponse:
    settings = get_settings()
    uid = upload_id or warehouse_store.get_active_upload_id()
    if not uid:
        raise ValueError("No warehouse upload found.")

    warehouse_store.clear_auto_aliases_for_upload(uid)
    warehouse_store.clear_discover_cache(uid)
    materials = warehouse_store.list_materials(uid)
    unresolved: list[tuple[int, str]] = []

    for mat in materials:
        existing = warehouse_store.get_aliases(mat.id)
        if existing and existing[0].source == "manual":
            continue

        resolved = _resolve_one_material(
            mat.raw_name,
            settings.warehouse_fuzzy_threshold,
            settings.warehouse_embed_threshold,
        )
        if resolved:
            can, source, conf = resolved
            warehouse_store.save_alias(mat.id, can, source, conf)
        else:
            unresolved.append((mat.id, mat.raw_name))

    if unresolved:
        names = [r for _, r in unresolved]
        llm_map = _llm_batch_resolve(names)
        for mid, raw in unresolved:
            key = raw.lower()
            if key in llm_map:
                can, conf = llm_map[key]
                warehouse_store.save_alias(mid, canonical_key(can), "llm", conf)

    rows: list[WarehouseMaterialRow] = []
    resolved = 0
    needs_review = 0
    for mat in materials:
        aliases = warehouse_store.get_aliases(mat.id)
        if aliases:
            a = aliases[0]
            needs = a.confidence < settings.warehouse_review_threshold and a.source != "manual"
            if needs:
                needs_review += 1
            else:
                resolved += 1
            rows.append(
                WarehouseMaterialRow(
                    id=mat.id,
                    raw_name=mat.raw_name,
                    sku=mat.sku,
                    qty=mat.qty,
                    canonical_name=a.canonical_name,
                    alias_source=a.source,  # type: ignore[arg-type]
                    confidence=a.confidence,
                    needs_review=needs,
                )
            )
        else:
            needs_review += 1
            rows.append(
                WarehouseMaterialRow(
                    id=mat.id,
                    raw_name=mat.raw_name,
                    sku=mat.sku,
                    qty=mat.qty,
                    needs_review=True,
                )
            )

    return ResolveResponse(
        upload_id=uid,
        resolved=resolved,
        needs_review=needs_review,
        materials=rows,
    )
