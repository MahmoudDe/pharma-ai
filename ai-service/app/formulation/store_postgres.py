"""PostgreSQL persistence for structured formulations."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Iterator

from app.formulation.schemas import FormulationRecord, IngredientLine
from app.formulation.store_base import FormulationSearchFilters


logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS formulations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    product_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    doc_id TEXT NOT NULL,
    doc_title TEXT,
    pdf_page INTEGER NOT NULL,
    printed_page INTEGER,
    source_text TEXT NOT NULL,
    procedure JSONB NOT NULL DEFAULT '[]'::jsonb,
    vector_text TEXT NOT NULL DEFAULT '',
    extraction_method TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    ingredient_cost_total DOUBLE PRECISION,
    markets JSONB
);
CREATE TABLE IF NOT EXISTS ingredients (
    id SERIAL PRIMARY KEY,
    formulation_id TEXT NOT NULL REFERENCES formulations(id) ON DELETE CASCADE,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    amount DOUBLE PRECISION,
    unit TEXT,
    phase TEXT
);
CREATE INDEX IF NOT EXISTS idx_formulations_doc ON formulations(doc_id);
CREATE INDEX IF NOT EXISTS idx_formulations_product_types ON formulations USING GIN (product_types);
CREATE INDEX IF NOT EXISTS idx_ingredients_norm ON ingredients(normalized_name);
CREATE INDEX IF NOT EXISTS idx_ingredients_raw ON ingredients(raw_name);
CREATE INDEX IF NOT EXISTS idx_ingredients_formulation ON ingredients(formulation_id);
"""


class PostgresFormulationStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA_SQL)
            conn.commit()

    def upsert(self, record: FormulationRecord) -> None:
        self.init_db()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO formulations
                (id, name, product_types, doc_id, doc_title, pdf_page, printed_page,
                 source_text, procedure, vector_text, extraction_method, confidence)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    product_types = EXCLUDED.product_types,
                    doc_id = EXCLUDED.doc_id,
                    doc_title = EXCLUDED.doc_title,
                    pdf_page = EXCLUDED.pdf_page,
                    printed_page = EXCLUDED.printed_page,
                    source_text = EXCLUDED.source_text,
                    procedure = EXCLUDED.procedure,
                    vector_text = EXCLUDED.vector_text,
                    extraction_method = EXCLUDED.extraction_method,
                    confidence = EXCLUDED.confidence
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
            conn.execute(
                "DELETE FROM ingredients WHERE formulation_id = %s", (record.id,)
            )
            for ing in record.ingredients:
                conn.execute(
                    """
                    INSERT INTO ingredients
                    (formulation_id, raw_name, normalized_name, amount, unit, phase)
                    VALUES (%s, %s, %s, %s, %s, %s)
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

    def _rows_to_records(self, conn, rows: list[dict]) -> list[FormulationRecord]:
        out: list[FormulationRecord] = []
        for row in rows:
            ings = conn.execute(
                "SELECT * FROM ingredients WHERE formulation_id = %s ORDER BY id",
                (row["id"],),
            ).fetchall()
            out.append(self._row_to_record(row, ings))
        return out

    def _row_to_record(self, row: dict, ings: list[dict]) -> FormulationRecord:
        product_types = row["product_types"]
        if isinstance(product_types, str):
            product_types = json.loads(product_types or "[]")
        procedure = row["procedure"]
        if isinstance(procedure, str):
            procedure = json.loads(procedure or "[]")
        return FormulationRecord(
            id=row["id"],
            name=row["name"],
            product_types=list(product_types or []),
            doc_id=row["doc_id"],
            doc_title=row["doc_title"] or "",
            pdf_page=int(row["pdf_page"]),
            printed_page=row["printed_page"],
            source_text=row["source_text"],
            procedure=list(procedure or []),
            vector_text=row["vector_text"] or "",
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

    def get(self, formulation_id: str) -> FormulationRecord | None:
        self.init_db()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM formulations WHERE id = %s", (formulation_id,)
            ).fetchone()
            if row is None:
                return None
            ings = conn.execute(
                "SELECT * FROM ingredients WHERE formulation_id = %s ORDER BY id",
                (formulation_id,),
            ).fetchall()
        return self._row_to_record(row, ings)

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
            clauses.append("f.doc_id = %s")
            params.append(filters.doc_id)
        if filters.ingredient:
            clauses.append(
                "(lower(i.normalized_name) LIKE %s OR lower(i.raw_name) LIKE %s)"
            )
            needle = f"%{filters.ingredient.lower()}%"
            params.extend([needle, needle])
        if required_types:
            clauses.append("f.product_types ?& %s::text[]")
            params.append(required_types)
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
                        lower(bi.raw_name) LIKE %s
                        OR lower(COALESCE(bi.normalized_name, '')) LIKE %s
                    )
                )
                """
            )
            needle = f"%{b}%"
            params.extend([needle, needle])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY f.confidence DESC LIMIT %s"
        params.append(filters.limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return self._rows_to_records(conn, rows)

    def count(self) -> int:
        self.init_db()
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM formulations").fetchone()
        return int(row["n"] if row else 0)

    def delete(self, formulation_id: str) -> bool:
        self.init_db()
        with self._connect() as conn:
            conn.execute("DELETE FROM ingredients WHERE formulation_id = %s", (formulation_id,))
            cur = conn.execute("DELETE FROM formulations WHERE id = %s", (formulation_id,))
            conn.commit()
        return cur.rowcount > 0

    def clear_all(self) -> int:
        self.init_db()
        with self._connect() as conn:
            n_form = conn.execute("SELECT COUNT(*) AS n FROM formulations").fetchone()
            conn.execute("DELETE FROM ingredients")
            conn.execute("DELETE FROM formulations")
            conn.commit()
        removed = int(n_form["n"] if n_form else 0)
        logger.info("Cleared PostgreSQL formulations (%d rows).", removed)
        return removed

    def backend_name(self) -> str:
        return "postgres"

    def iter_all_formulations(self) -> Iterator[FormulationRecord]:
        """Yield all formulations (for migration tooling)."""
        self.init_db()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM formulations ORDER BY id").fetchall()
            for rec in self._rows_to_records(conn, rows):
                yield rec
