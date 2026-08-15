#!/usr/bin/env python3
"""Retag product_types on SQLite formulas + Qdrant payloads (no re-embed)."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.ingestion.index import get_client
from app.ingestion.metadata import infer_product_types


def retag_sqlite(db_path: Path) -> int:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, name, product_types, source_text FROM formulations"
    ).fetchall()
    updated = 0
    for row in rows:
        old = json.loads(row["product_types"] or "[]")
        new = infer_product_types(row["source_text"] or "", row["name"] or "")
        if not new:
            continue
        merged = list(dict.fromkeys([*old, *new]))
        if merged == old:
            continue
        con.execute(
            "UPDATE formulations SET product_types = ? WHERE id = ?",
            (json.dumps(merged), row["id"]),
        )
        updated += 1
    con.commit()
    con.close()
    return updated


def retag_qdrant() -> int:
    settings = get_settings()
    client = get_client()
    updated = 0
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=128,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        for point in points:
            payload = point.payload or {}
            text = str(payload.get("text") or "")
            title = payload.get("section_title") or payload.get("formula_name")
            old = [str(p) for p in (payload.get("product_types") or [])]
            new = infer_product_types(text, str(title) if title else None)
            if not new:
                continue
            merged = list(dict.fromkeys([*old, *new]))
            if merged == old:
                continue
            client.set_payload(
                collection_name=settings.qdrant_collection,
                payload={"product_types": merged},
                points=[point.id],
            )
            updated += 1
        if offset is None:
            break
    return updated


def main() -> int:
    db = ROOT / "data" / "formulations.db"
    sqlite_n = retag_sqlite(db) if db.is_file() else 0
    print(f"SQLite formulations retagged: {sqlite_n}")
    qdrant_n = retag_qdrant()
    print(f"Qdrant payloads retagged: {qdrant_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
