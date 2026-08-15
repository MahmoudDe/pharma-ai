from __future__ import annotations

import sqlite3
from pathlib import Path

from app.kbs.schemas import ValidationReport


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "kbs_reports.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                formulation_id TEXT PRIMARY KEY,
                precision_score REAL NOT NULL,
                status TEXT NOT NULL,
                report_json TEXT NOT NULL,
                validated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_report(report: ValidationReport) -> None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO reports (formulation_id, precision_score, status, report_json, validated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(formulation_id) DO UPDATE SET
                precision_score = excluded.precision_score,
                status = excluded.status,
                report_json = excluded.report_json,
                validated_at = excluded.validated_at
            """,
            (
                report.formulation_id,
                report.precision_score,
                report.status,
                report.model_dump_json(),
                report.validated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_report(formulation_id: str) -> ValidationReport | None:
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT report_json FROM reports WHERE formulation_id = ?",
            (formulation_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return ValidationReport.model_validate_json(row[0])


def get_verdicts(formulation_ids: list[str]) -> dict[str, tuple[float, str]]:
    """Lightweight lookup: id -> (precision_score, status) for badge rendering."""
    if not formulation_ids or not DB_PATH.exists():
        return {}
    placeholders = ",".join("?" for _ in formulation_ids)
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            f"SELECT formulation_id, precision_score, status FROM reports "
            f"WHERE formulation_id IN ({placeholders})",
            formulation_ids,
        ).fetchall()
    finally:
        conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def delete_report(formulation_id: str) -> bool:
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("DELETE FROM reports WHERE formulation_id = ?", (formulation_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_reports() -> int:
    if not DB_PATH.exists():
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    finally:
        conn.close()


def list_reports_by_status(
    statuses: list[str],
    *,
    limit: int = 100,
) -> list[tuple[str, float, str]]:
    if not statuses or not DB_PATH.is_file():
        return []
    placeholders = ",".join("?" for _ in statuses)
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            f"""
            SELECT formulation_id, precision_score, status
            FROM reports
            WHERE status IN ({placeholders})
            ORDER BY precision_score ASC
            LIMIT ?
            """,
            (*statuses, limit),
        ).fetchall()
    finally:
        conn.close()
    return [(r[0], float(r[1]), r[2]) for r in rows]
