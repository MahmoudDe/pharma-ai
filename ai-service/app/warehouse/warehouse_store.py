"""SQLite persistence for warehouse uploads and alias resolution."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import PROJECT_ROOT


DB_PATH = PROJECT_ROOT / "data" / "warehouse.db"

_NAME_COLUMNS = ("material", "ingredient", "name", "description", "item", "product", "raw")


@dataclass(slots=True)
class MaterialRow:
    id: int
    upload_id: str
    raw_name: str
    sku: str | None
    qty: float | None


@dataclass(slots=True)
class AliasRow:
    warehouse_material_id: int
    canonical_name: str
    source: str
    confidence: float


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS warehouse_uploads (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS warehouse_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id TEXT NOT NULL,
                raw_name TEXT NOT NULL,
                sku TEXT,
                qty REAL,
                FOREIGN KEY (upload_id) REFERENCES warehouse_uploads(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS material_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_material_id INTEGER NOT NULL,
                canonical_name TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY (warehouse_material_id) REFERENCES warehouse_materials(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS material_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_material_id INTEGER NOT NULL,
                matched_ingredient_norm TEXT NOT NULL,
                formulation_corpus_hit INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (warehouse_material_id) REFERENCES warehouse_materials(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS discover_cache (
                upload_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alias_overrides (
                raw_key TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_wh_materials_upload ON warehouse_materials(upload_id);
            """
        )
        conn.commit()


def new_upload_id() -> str:
    return str(uuid.uuid4())


def replace_active_upload(filename: str, rows: list[tuple[str, str | None, float | None]]) -> str:
    """MVP: clear prior uploads and store one active inventory."""
    init_db()
    upload_id = new_upload_id()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("DELETE FROM discover_cache")
        conn.execute("DELETE FROM material_matches")
        conn.execute("DELETE FROM material_aliases")
        conn.execute("DELETE FROM warehouse_materials")
        conn.execute("DELETE FROM warehouse_uploads")
        conn.execute(
            "INSERT INTO warehouse_uploads (id, filename, uploaded_at, row_count) VALUES (?, ?, ?, ?)",
            (upload_id, filename, now, len(rows)),
        )
        for raw_name, sku, qty in rows:
            conn.execute(
                "INSERT INTO warehouse_materials (upload_id, raw_name, sku, qty) VALUES (?, ?, ?, ?)",
                (upload_id, raw_name, sku, qty),
            )
        conn.commit()
    return upload_id


def get_active_upload_id() -> str | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM warehouse_uploads ORDER BY uploaded_at DESC LIMIT 1"
        ).fetchone()
    return str(row["id"]) if row else None


def list_materials(upload_id: str | None = None) -> list[MaterialRow]:
    init_db()
    uid = upload_id or get_active_upload_id()
    if not uid:
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, upload_id, raw_name, sku, qty FROM warehouse_materials WHERE upload_id = ? ORDER BY id",
            (uid,),
        ).fetchall()
    return [
        MaterialRow(
            id=int(r["id"]),
            upload_id=str(r["upload_id"]),
            raw_name=str(r["raw_name"]),
            sku=r["sku"],
            qty=r["qty"],
        )
        for r in rows
    ]


def get_material(material_id: int) -> MaterialRow | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, upload_id, raw_name, sku, qty FROM warehouse_materials WHERE id = ?",
            (material_id,),
        ).fetchone()
    if not row:
        return None
    return MaterialRow(
        id=int(row["id"]),
        upload_id=str(row["upload_id"]),
        raw_name=str(row["raw_name"]),
        sku=row["sku"],
        qty=row["qty"],
    )


def alias_override_key(raw_name: str) -> str:
    from app.formulation.normalize import normalize_ingredient_name
    from app.warehouse.arabic_aliases import has_arabic
    from app.warehouse.matching import canonical_key

    stripped = raw_name.strip()
    if has_arabic(stripped):
        return stripped.lower()
    norm = normalize_ingredient_name(stripped)
    return canonical_key(norm or stripped)


def save_alias_override(raw_name: str, canonical: str) -> None:
    from app.warehouse.matching import canonical_key

    key = alias_override_key(raw_name)
    canonical = canonical_key(canonical)
    now = datetime.now(timezone.utc).isoformat()
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO alias_overrides (raw_key, canonical_name, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, canonical, now),
        )
        conn.commit()


def get_alias_override(raw_name: str) -> str | None:
    key = alias_override_key(raw_name)
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT canonical_name FROM alias_overrides WHERE raw_key = ?",
            (key,),
        ).fetchone()
    return str(row["canonical_name"]) if row else None


def clear_aliases_for_upload(upload_id: str) -> None:
    """Remove auto-resolved aliases; keep manual corrections."""
    clear_auto_aliases_for_upload(upload_id)


def clear_auto_aliases_for_upload(upload_id: str) -> None:
    init_db()
    with _connect() as conn:
        ids = [
            int(r[0])
            for r in conn.execute(
                "SELECT id FROM warehouse_materials WHERE upload_id = ?", (upload_id,)
            ).fetchall()
        ]
        for mid in ids:
            conn.execute(
                """
                DELETE FROM material_aliases
                WHERE warehouse_material_id = ? AND source NOT IN ('manual')
                """,
                (mid,),
            )
            conn.execute(
                "DELETE FROM material_matches WHERE warehouse_material_id = ?",
                (mid,),
            )
            row = conn.execute(
                "SELECT canonical_name FROM material_aliases WHERE warehouse_material_id = ? LIMIT 1",
                (mid,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    INSERT INTO material_matches (warehouse_material_id, matched_ingredient_norm, formulation_corpus_hit)
                    VALUES (?, ?, 1)
                    """,
                    (mid, str(row["canonical_name"])),
                )
        conn.commit()


def save_alias(material_id: int, canonical: str, source: str, confidence: float) -> None:
    from app.warehouse.matching import canonical_key

    canonical = canonical_key(canonical)
    init_db()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM material_aliases WHERE warehouse_material_id = ?",
            (material_id,),
        )
        conn.execute(
            """
            INSERT INTO material_aliases (warehouse_material_id, canonical_name, source, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (material_id, canonical, source, confidence),
        )
        conn.execute(
            "DELETE FROM material_matches WHERE warehouse_material_id = ?",
            (material_id,),
        )
        conn.execute(
            """
            INSERT INTO material_matches (warehouse_material_id, matched_ingredient_norm, formulation_corpus_hit)
            VALUES (?, ?, 1)
            """,
            (material_id, canonical),
        )
        conn.commit()


def get_aliases(material_id: int) -> list[AliasRow]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT warehouse_material_id, canonical_name, source, confidence
            FROM material_aliases WHERE warehouse_material_id = ?
            ORDER BY confidence DESC LIMIT 1
            """,
            (material_id,),
        ).fetchall()
    return [
        AliasRow(
            warehouse_material_id=int(r["warehouse_material_id"]),
            canonical_name=str(r["canonical_name"]),
            source=str(r["source"]),
            confidence=float(r["confidence"]),
        )
        for r in rows
    ]


def get_canonical_inventory(upload_id: str) -> set[str]:
    """Resolved canonical names for discovery (normalized keys)."""
    from app.warehouse.matching import canonical_key

    inv: set[str] = set()
    for mat in list_materials(upload_id):
        aliases = get_aliases(mat.id)
        if aliases:
            inv.add(canonical_key(aliases[0].canonical_name))
        else:
            n = canonical_key(mat.raw_name)
            if n:
                inv.add(n)
    return inv


def cache_discover(upload_id: str, payload: dict) -> None:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO discover_cache (upload_id, payload_json, created_at)
            VALUES (?, ?, ?)
            """,
            (upload_id, json.dumps(payload), now),
        )
        conn.commit()


def clear_discover_cache(upload_id: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM discover_cache WHERE upload_id = ?", (upload_id,))
        conn.commit()


def get_discover_cache(upload_id: str) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM discover_cache WHERE upload_id = ?", (upload_id,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["payload_json"])
