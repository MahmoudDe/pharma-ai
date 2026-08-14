"""Source PDF mapping and manual alias API."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.ingestion.extract import doc_id_from_path
from app.main import app
from app.sources.pdf_map import pdf_index, resolve_pdf_path
from app.warehouse import warehouse_store


client = TestClient(app)


def test_pdf_index_maps_doc_ids():
    index = pdf_index()
    assert isinstance(index, dict)
    for doc_id, path in index.items():
        assert path.suffix.lower() == ".pdf"
        assert doc_id == doc_id_from_path(path)


def test_resolve_pdf_path_known_doc():
    index = pdf_index()
    if not index:
        return
    doc_id, path = next(iter(index.items()))
    assert resolve_pdf_path(doc_id) == path


def test_sources_endpoint_returns_pdf():
    index = pdf_index()
    if not index:
        return
    doc_id = next(iter(index))
    response = client.get(f"/sources/{doc_id}")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/pdf")


def test_manual_alias_override(tmp_path, monkeypatch):
    monkeypatch.setattr(warehouse_store, "DB_PATH", tmp_path / "wh_test.db")
    warehouse_store.init_db()
    uid = warehouse_store.replace_active_upload("t.csv", [("Mystery Oil", None, 1.0)])
    mats = warehouse_store.list_materials(uid)
    assert len(mats) == 1
    mid = mats[0].id
    response = client.patch(
        f"/warehouse/materials/{mid}",
        json={"canonical_name": "Mineral Oil"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["canonical_name"] == "mineral oil"
    assert body["alias_source"] == "manual"
    assert body["needs_review"] is False
    assert warehouse_store.get_alias_override("Mystery Oil") == "mineral oil"
