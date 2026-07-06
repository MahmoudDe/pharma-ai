"""Tests for formulation store backends."""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.formulation.store_base import FormulationSearchFilters
from app.formulation.store_sqlite import DB_PATH, SQLiteFormulationStore


@pytest.fixture()
def sqlite_store(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("app.formulation.store_sqlite.DB_PATH", db_path)
    store = SQLiteFormulationStore()
    store.init_db()
    return store


def _sample_record(**kwargs) -> FormulationRecord:
    rid = kwargs.pop("id", str(uuid.uuid4()))
    return FormulationRecord(
        id=rid,
        name=kwargs.pop("name", "Baby Shampoo"),
        product_types=kwargs.pop("product_types", ["baby", "shampoo"]),
        doc_id=kwargs.pop("doc_id", "test_doc"),
        pdf_page=1,
        source_text="sample",
        ingredients=kwargs.pop(
            "ingredients",
            [
                IngredientLine(raw_name="Water", normalized_name="water", amount=70.0, unit="%"),
                IngredientLine(raw_name="SLS", normalized_name="sodium lauryl sulfate", amount=10.0, unit="%"),
            ],
        ),
        confidence=0.9,
        **kwargs,
    )


def test_sqlite_upsert_and_get(sqlite_store):
    rec = _sample_record()
    sqlite_store.upsert(rec)
    loaded = sqlite_store.get(rec.id)
    assert loaded is not None
    assert loaded.name == "Baby Shampoo"
    assert len(loaded.ingredients) == 2


def test_sqlite_banned_ingredient_filter(sqlite_store):
    clean = _sample_record(name="Gentle Shampoo", ingredients=[
        IngredientLine(raw_name="Water", normalized_name="water", amount=90.0, unit="%"),
        IngredientLine(raw_name="Cocamidopropyl Betaine", normalized_name="capb", amount=10.0, unit="%"),
    ])
    with_sls = _sample_record(name="Classic Shampoo")
    sqlite_store.upsert(clean)
    sqlite_store.upsert(with_sls)

    results = sqlite_store.search(
        FormulationSearchFilters(banned_ingredients=["sls"], limit=10)
    )
    names = {r.name for r in results}
    assert "Gentle Shampoo" in names
    assert "Baby Shampoo" not in names


def test_sqlite_product_type_filter(sqlite_store):
    shampoo = _sample_record(name="Shampoo A", product_types=["shampoo"])
    cream = _sample_record(name="Hand Cream", product_types=["cream"])
    sqlite_store.upsert(shampoo)
    sqlite_store.upsert(cream)

    results = sqlite_store.search(
        FormulationSearchFilters(product_types=["cream"], limit=10)
    )
    assert len(results) == 1
    assert results[0].name == "Hand Cream"


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)
def test_postgres_roundtrip():
    from app.formulation.store_postgres import PostgresFormulationStore

    store = PostgresFormulationStore(os.environ["DATABASE_URL"])
    store.clear_all()
    rec = _sample_record()
    store.upsert(rec)
    assert store.count() == 1
    loaded = store.get(rec.id)
    assert loaded is not None
    assert loaded.name == rec.name

    banned = store.search(
        FormulationSearchFilters(banned_ingredients=["sls"], limit=10)
    )
    assert len(banned) == 0
