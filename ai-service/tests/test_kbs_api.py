"""Tests for the /kbs API endpoints."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import kbs as kbs_api
from tests.test_kbs_rules import make_record


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.kbs.report_store.DB_PATH", tmp_path / "kbs_reports.db")
    app = FastAPI()
    app.include_router(kbs_api.router)
    return TestClient(app)


def test_list_rules(client):
    response = client.get("/kbs/rules")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 10
    families = {rule["family"] for rule in body["rules"]}
    assert {"completeness", "consistency", "ranges", "fidelity"} <= families


def test_validate_unknown_formulation_404(client, monkeypatch):
    monkeypatch.setattr("app.api.kbs.get_formulation", lambda _id: None)
    response = client.post("/kbs/validate/nope")
    assert response.status_code == 404


def test_validate_and_fetch_report(client, monkeypatch):
    record = make_record(id="api1")
    monkeypatch.setattr("app.api.kbs.get_formulation", lambda _id: record)

    class FakeStore:
        def upsert(self, rec):
            pass

    monkeypatch.setattr("app.kbs.service.get_store", lambda: FakeStore())

    response = client.post("/kbs/validate/api1", json={"markets": []})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["precision_score"] == 1.0

    fetched = client.get("/kbs/report/api1")
    assert fetched.status_code == 200
    assert fetched.json()["formulation_id"] == "api1"

    stats = client.get("/kbs/stats")
    assert stats.status_code == 200
    assert stats.json()["reports"] == 1


def test_report_missing_404(client):
    response = client.get("/kbs/report/ghost")
    assert response.status_code == 404
