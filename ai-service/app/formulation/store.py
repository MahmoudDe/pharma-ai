"""SQLite persistence for structured formulations."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from pathlib import Path

from app.config import PROJECT_ROOT
from app.formulation.schemas import FormulationRecord, IngredientLine
from app.retrieval.intent import QueryIntent


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


def clear_all_formulations() -> int:
    """Delete all structured formulations (used with run_ingest --force)."""
    init_db()
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


def init_db() -> None:
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


def upsert_formulation(record: FormulationRecord) -> None:
    init_db()
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


def get_formulation(formulation_id: str) -> FormulationRecord | None:
    init_db()
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


def _name_relevance_score(name: str, intent: QueryIntent, query: str) -> float:
    name_lower = name.lower()
    query_lower = query.lower()
    score = 0.0
    if "baby" in intent.product_types and "shampoo" in intent.product_types:
        if "baby" in name_lower and "shampoo" in name_lower:
            score += 3.0
        elif "baby" in name_lower and "bath" in name_lower:
            score -= 2.0
    if "anti_dandruff" in intent.product_types:
        if "anti" in name_lower and "dandruff" in name_lower.replace("-", ""):
            score += 3.0
        elif "antidandruff" in name_lower.replace(" ", ""):
            score += 3.0
        if "shampoo" in intent.product_types:
            compact = name_lower.replace(" ", "").replace("-", "")
            if "shampoo" in name_lower or "shamdoo" in compact or "shamwoo" in compact:
                score += 3.0
            elif "cream" in name_lower:
                score -= 2.5
            elif "lotion" in name_lower:
                score -= 2.0
    if re.search(r"\bhand\s+cream\b", query_lower, re.I):
        if re.search(r"\btube[-\s]?dispensed\b", name_lower, re.I):
            score += 4.0
        elif re.search(r"\bhand\s+(and\s+)?(nail\s+)?cream\b", name_lower, re.I):
            score += 2.5
    for kw in intent.keywords:
        if len(kw) >= 4 and kw in name_lower:
            score += 0.5
    return score


def list_formulations(
    *,
    product_types: list[str] | None = None,
    product_type: str | None = None,
    ingredient: str | None = None,
    doc_id: str | None = None,
    limit: int = 20,
) -> list[FormulationRecord]:
    init_db()
    required_types = list(product_types or [])
    if product_type and product_type not in required_types:
        required_types.append(product_type)

    sql = "SELECT DISTINCT f.* FROM formulations f"
    joins: list[str] = []
    params: list[object] = []
    if ingredient:
        joins.append("JOIN ingredients i ON i.formulation_id = f.id")
    if joins:
        sql += " " + " ".join(joins)
    clauses: list[str] = []
    if doc_id:
        clauses.append("f.doc_id = ?")
        params.append(doc_id)
    if ingredient:
        clauses.append("(i.normalized_name LIKE ? OR i.raw_name LIKE ?)")
        needle = f"%{ingredient.lower()}%"
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
    return out[:limit]


def _structured_product_filter(intent: QueryIntent) -> list[str] | None:
    types = list(intent.product_types)
    if "anti_dandruff" in types and "shampoo" in types:
        return ["anti_dandruff"]
    if "baby" in types and "shampoo" in types:
        return ["baby", "shampoo"]
    return types or None


def search_by_intent(intent: QueryIntent, query: str = "", limit: int = 3) -> list[FormulationRecord]:
    if not intent.wants_formula and not intent.product_types:
        return []

    filter_types = _structured_product_filter(intent)
    records = list_formulations(
        product_types=filter_types,
        ingredient=None,
        limit=limit * 8,
    )

    if not records and intent.product_types:
        for pt in intent.product_types:
            records.extend(list_formulations(product_type=pt, limit=limit * 4))

    query_lower = query.lower()
    scored: list[tuple[float, FormulationRecord]] = []
    for rec in records:
        if len(rec.ingredients) < 2:
            continue
        relevance = _name_relevance_score(rec.name, intent, query)
        ing_bonus = min(len(rec.ingredients), 24) * 0.06
        if re.search(r"\bhand\s+cream\b", query_lower, re.I) and re.search(
            r"\btube[-\s]?dispensed\b", rec.name, re.I
        ):
            relevance += 5.0
        scored.append((rec.confidence + relevance * 0.2 + ing_bonus, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_by_name: dict[str, FormulationRecord] = {}
    for _, rec in scored:
        key = rec.name.lower()[:80]
        prev = best_by_name.get(key)
        if prev is None or len(rec.ingredients) > len(prev.ingredients):
            best_by_name[key] = rec

    out = sorted(best_by_name.values(), key=lambda r: next(s for s, rec in scored if rec.id == r.id), reverse=True)
    # Re-sort by computed score
    score_map = {rec.id: sc for sc, rec in scored}
    out.sort(key=lambda r: score_map.get(r.id, 0.0), reverse=True)
    return out[:limit]


def new_formulation_id() -> str:
    return str(uuid.uuid4())
