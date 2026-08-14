"""Phase D: warehouse overrides, embedding alias fallback, constraint-aware discover."""
from __future__ import annotations

import numpy as np

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.warehouse import warehouse_store
from app.warehouse.alias_resolve import resolve_upload
from app.warehouse.embedding_match import embedding_canonical
from app.warehouse.match_products import discover_products
from app.warehouse.schemas import DiscoverRequest


def _formulation(
    fid: str,
    name: str,
    ingredients: list[tuple[str, str, float]],
) -> FormulationRecord:
    return FormulationRecord(
        id=fid,
        name=name,
        product_types=["shampoo"],
        doc_id="doc",
        pdf_page=1,
        source_text=name,
        ingredients=[
            IngredientLine(
                raw_name=raw,
                normalized_name=norm,
                amount=amt,
                unit="%",
            )
            for raw, norm, amt in ingredients
        ],
    )


def test_alias_override_key_and_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(warehouse_store, "DB_PATH", tmp_path / "wh_override.db")
    warehouse_store.init_db()
    warehouse_store.save_alias_override("Trade X", "Glyceryl Stearate")
    assert warehouse_store.get_alias_override("Trade X") == "glyceryl stearate"


def test_resolve_uses_learned_override(tmp_path, monkeypatch):
    monkeypatch.setattr(warehouse_store, "DB_PATH", tmp_path / "wh_resolve.db")
    warehouse_store.init_db()
    uid = warehouse_store.replace_active_upload("t.csv", [("Trade X", None, 1.0)])
    warehouse_store.save_alias_override("Trade X", "glycerin")

    monkeypatch.setattr("app.warehouse.alias_resolve._fuzzy_canonical", lambda *a: None)
    monkeypatch.setattr("app.warehouse.alias_resolve.embedding_canonical", lambda *a, **k: None)
    monkeypatch.setattr("app.warehouse.alias_resolve._llm_batch_resolve", lambda names: {})

    res = resolve_upload(uid)
    row = res.materials[0]
    assert row.canonical_name == "glycerin"
    assert row.alias_source == "override"
    assert row.needs_review is False


def test_resolve_preserves_manual_alias_on_re_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(warehouse_store, "DB_PATH", tmp_path / "wh_manual.db")
    warehouse_store.init_db()
    uid = warehouse_store.replace_active_upload("t.csv", [("Mystery Oil", None, 1.0)])
    mid = warehouse_store.list_materials(uid)[0].id
    warehouse_store.save_alias(mid, "mineral oil", "manual", 1.0)

    monkeypatch.setattr(
        "app.warehouse.alias_resolve._resolve_one_material",
        lambda raw, ft, et: ("sodium laureth sulfate", "corpus", 0.9),
    )
    monkeypatch.setattr("app.warehouse.alias_resolve._llm_batch_resolve", lambda names: {})

    res = resolve_upload(uid)
    assert res.materials[0].canonical_name == "mineral oil"
    assert res.materials[0].alias_source == "manual"


def test_resolve_uses_embedding_before_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(warehouse_store, "DB_PATH", tmp_path / "wh_embed.db")
    warehouse_store.init_db()
    uid = warehouse_store.replace_active_upload("t.csv", [("Vague trade name", None, 1.0)])

    monkeypatch.setattr("app.warehouse.alias_resolve._rules_canonical", lambda raw: None)
    monkeypatch.setattr("app.warehouse.alias_resolve._fuzzy_canonical", lambda *a: None)
    monkeypatch.setattr(
        "app.warehouse.alias_resolve.embedding_canonical",
        lambda raw, threshold=None: ("glycerin", 0.85),
    )
    monkeypatch.setattr("app.warehouse.alias_resolve._llm_batch_resolve", lambda names: {})

    res = resolve_upload(uid)
    assert res.materials[0].alias_source == "embedding"
    assert res.materials[0].canonical_name == "glycerin"


def test_embedding_canonical_with_mock_vectors(monkeypatch):
    labels = ("glycerin", "water")
    vectors = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    monkeypatch.setattr(
        "app.warehouse.embedding_match._corpus_embedding_index",
        lambda: (labels, vectors),
    )
    monkeypatch.setattr(
        "app.ingestion.embed.embed_query",
        lambda text: np.array([0.95, 0.05], dtype=np.float32),
    )
    hit = embedding_canonical("gly", threshold=0.5)
    assert hit is not None
    assert hit[0] == "glycerin"


def test_discover_excludes_banned_ingredient(monkeypatch):
    clean = _formulation(
        "f-clean",
        "Clean Shampoo",
        [
            ("Glycerin", "glycerin", 50.0),
            ("SLS", "sodium laureth sulfate", 50.0),
        ],
    )
    banned = _formulation(
        "f-bad",
        "Bad Shampoo",
        [
            ("Glycerin", "glycerin", 50.0),
            ("Formaldehyde", "formaldehyde", 50.0),
        ],
    )

    monkeypatch.setattr(
        "app.warehouse.match_products.list_formulations",
        lambda **kw: [clean, banned],
    )
    monkeypatch.setattr(
        warehouse_store,
        "get_canonical_inventory",
        lambda uid: {"glycerin", "sodium laureth sulfate"},
    )
    monkeypatch.setattr(warehouse_store, "get_discover_cache", lambda uid: None)
    monkeypatch.setattr(warehouse_store, "cache_discover", lambda uid, payload: None)

    req = DiscoverRequest(
        upload_id="u1",
        min_coverage=50,
        banned_ingredients=["formaldehyde"],
    )
    resp = discover_products(req)
    names = {p.name for p in resp.products}
    assert "Clean Shampoo" in names
    assert "Bad Shampoo" not in names


def test_discover_excludes_over_max_cost(monkeypatch):
    cheap = _formulation(
        "f-cheap",
        "Cheap Blend",
        [
            ("Water", "water", 95.0),
            ("Glycerin", "glycerin", 5.0),
        ],
    )
    rich = _formulation(
        "f-rich",
        "Rich Serum",
        [
            ("Water", "water", 50.0),
            ("Tocopherol", "tocopherol", 50.0),
        ],
    )

    monkeypatch.setattr(
        "app.warehouse.match_products.list_formulations",
        lambda **kw: [cheap, rich],
    )
    monkeypatch.setattr(
        warehouse_store,
        "get_canonical_inventory",
        lambda uid: {"water", "glycerin", "tocopherol"},
    )
    monkeypatch.setattr(warehouse_store, "get_discover_cache", lambda uid: None)
    monkeypatch.setattr(warehouse_store, "cache_discover", lambda uid, payload: None)

    req = DiscoverRequest(
        upload_id="u1",
        min_coverage=50,
        max_cost=1.0,
        exclude_water=False,
    )
    resp = discover_products(req)
    names = {p.name for p in resp.products}
    assert "Cheap Blend" in names
    assert "Rich Serum" not in names
