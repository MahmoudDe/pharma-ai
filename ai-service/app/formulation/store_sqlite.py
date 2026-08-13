"""SQLite persistence for structured formulations."""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path

from app.config import PROJECT_ROOT
from app.formulation.schemas import FormulationRecord, IngredientLine
from app.formulation.store_base import FormulationSearchFilters


logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "formulations.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(formulations)").fetchall()}
    if "procedure" not in cols:
        conn.execute("ALTER TABLE formulations ADD COLUMN procedure TEXT NOT NULL DEFAULT '[]'")
    if "vector_text" not in cols:
        conn.execute("ALTER TABLE formulations ADD COLUMN vector_text TEXT NOT NULL DEFAULT ''")


def _row_to_record(row: sqlite3.Row, ings: list[sqlite3.Row]) -> FormulationRecord:
    return FormulationRecord(
        id=row["id"],
        name=row["name"],
        product_types=json.loads(row["product_types"] or "[]"),
        doc_id=row["doc_id"],
        doc_title=row["doc_title"] or "",
        pdf_page=int(row["pdf_page"]),
        printed_page=row["printed_page"],
        source_text=row["source_text"],
        procedure=json.loads(row["procedure"] or "[]"),
        vector_text=(row["vector_text"] or "") if row["vector_text"] else "",
        extraction_method=row["extraction_method"],
        confidence=float(row["confidence"]),
        ingredients=[
            IngredientLine(
                raw_name=i["raw_name"],
                normalized_name=i["normalized_name"],
                amount=i["amount"],
                unit=i["unit"],
                phase=i["phase"],
            )
            for i in ings
        ],
    )


class SQLiteFormulationStore:
    def init_db(self) -> None:
        with _connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS formulations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    product_types TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    doc_title TEXT,
                    pdf_page INTEGER NOT NULL,
                    printed_page INTEGER,
                    source_text TEXT NOT NULL,
                    procedure TEXT NOT NULL DEFAULT '[]',
                    vector_text TEXT NOT NULL DEFAULT '',
                    extraction_method TEXT NOT NULL,
                    confidence REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    formulation_id TEXT NOT NULL,
                    raw_name TEXT NOT NULL,
                    normalized_name TEXT,
                    amount REAL,
                    unit TEXT,
                    phase TEXT,
                    FOREIGN KEY (formulation_id) REFERENCES formulations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_formulations_doc ON formulations(doc_id);
                CREATE INDEX IF NOT EXISTS idx_formulations_product ON formulations(product_types);
                CREATE INDEX IF NOT EXISTS idx_ingredients_norm ON ingredients(normalized_name);
                CREATE INDEX IF NOT EXISTS idx_ingredients_raw ON ingredients(raw_name);
                """
            )
            _migrate_schema(conn)
            conn.commit()

    def upsert(self, record: FormulationRecord) -> None:
        self.init_db()
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO formulations
                (id, name, product_types, doc_id, doc_title, pdf_page, printed_page,
                 source_text, procedure, vector_text, extraction_method, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.name,
                    json.dumps(record.product_types),
                    record.doc_id,
                    record.doc_title,
                    record.pdf_page,
                    record.printed_page,
                    record.source_text,
                    json.dumps(record.procedure),
                    record.vector_text,
                    record.extraction_method,
                    record.confidence,
                ),
            )
            conn.execute("DELETE FROM ingredients WHERE formulation_id = ?", (record.id,))
            for ing in record.ingredients:
                conn.execute(
                    """
                    INSERT INTO ingredients
                    (formulation_id, raw_name, normalized_name, amount, unit, phase)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        ing.raw_name,
                        ing.normalized_name,
                        ing.amount,
                        ing.unit,
                        ing.phase,
                    ),
                )
            conn.commit()

    def get(self, formulation_id: str) -> FormulationRecord | None:
        self.init_db()
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM formulations WHERE id = ?", (formulation_id,)
            ).fetchone()
            if row is None:
                return None
            ings = conn.execute(
                "SELECT * FROM ingredients WHERE formulation_id = ? ORDER BY id",
                (formulation_id,),
            ).fetchall()
        return _row_to_record(row, ings)

    def search(self, filters: FormulationSearchFilters) -> list[FormulationRecord]:
        self.init_db()
        required_types = filters.resolved_product_types()

        sql = "SELECT DISTINCT f.* FROM formulations f"
        joins: list[str] = []
        params: list[object] = []
        if filters.ingredient:
            joins.append("JOIN ingredients i ON i.formulation_id = f.id")
        if joins:
            sql += " " + " ".join(joins)
        clauses: list[str] = []
        if filters.doc_id:
            clauses.append("f.doc_id = ?")
            params.append(filters.doc_id)
        if filters.ingredient:
            clauses.append("(i.normalized_name LIKE ? OR i.raw_name LIKE ?)")
            needle = f"%{filters.ingredient.lower()}%"
            params.extend([needle, needle])
        for banned in filters.banned_ingredients or []:
            b = banned.lower().strip()
            if not b:
                continue
            clauses.append(
                """
                NOT EXISTS (
                    SELECT 1 FROM ingredients bi
                    WHERE bi.formulation_id = f.id
                    AND (
                        lower(bi.raw_name) LIKE ?
                        OR lower(COALESCE(bi.normalized_name, '')) LIKE ?
                    )
                )
                """
            )
            needle = f"%{b}%"
            params.extend([needle, needle])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            out: list[FormulationRecord] = []
            for row in rows:
                types = json.loads(row["product_types"] or "[]")
                if required_types and not all(t in types for t in required_types):
                    continue
                ings = conn.execute(
                    "SELECT * FROM ingredients WHERE formulation_id = ? ORDER BY id",
                    (row["id"],),
                ).fetchall()
                out.append(_row_to_record(row, ings))

        out.sort(key=lambda r: r.confidence, reverse=True)
        return out[: filters.limit]

    def count(self) -> int:
        self.init_db()
        with _connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM formulations").fetchone()
        return int(row[0] if row else 0)

    def delete(self, formulation_id: str) -> bool:
        self.init_db()
        with _connect() as conn:
            conn.execute("DELETE FROM ingredients WHERE formulation_id = ?", (formulation_id,))
            cur = conn.execute("DELETE FROM formulations WHERE id = ?", (formulation_id,))
            conn.commit()
        return cur.rowcount > 0

    def clear_all(self) -> int:
        self.init_db()
        with _connect() as conn:
            n_ing = conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0]
            n_form = conn.execute("SELECT COUNT(*) FROM formulations").fetchone()[0]
            conn.execute("DELETE FROM ingredients")
            conn.execute("DELETE FROM formulations")
            conn.commit()
        removed = int(n_form or 0)
        logger.info(
            "Cleared formulations DB (%d formulations, %d ingredient rows).",
            removed,
            int(n_ing or 0),
        )
        return removed

    def backend_name(self) -> str:
        return "sqlite"


def new_formulation_id() -> str:
    return str(uuid.uuid4())
