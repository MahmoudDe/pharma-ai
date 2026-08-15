#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys

from app.config import get_settings
from app.formulation.store_sqlite import SQLiteFormulationStore
from app.formulation.store_postgres import PostgresFormulationStore


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Copy formulations SQLite -> PostgreSQL")
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL URL (defaults to DATABASE_URL from env)",
    )
    parser.add_argument(
        "--clear-target",
        action="store_true",
        help="Delete all rows in PostgreSQL before import",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    database_url = args.database_url or settings.database_url
    if not database_url:
        logger.error("Set DATABASE_URL or pass --database-url")
        return 1

    source = SQLiteFormulationStore()
    target = PostgresFormulationStore(database_url)
    target.init_db()

    if args.clear_target:
        target.clear_all()

    n = 0
    for rec in _iter_sqlite(source):
        target.upsert(rec)
        n += 1
        if n % 50 == 0:
            logger.info("Migrated %d formulations...", n)

    logger.info("Done. Migrated %d formulations to PostgreSQL.", n)
    return 0


def _iter_sqlite(store: SQLiteFormulationStore):
    import json
    import sqlite3
    from app.formulation.store_sqlite import DB_PATH as SQLITE_PATH

    store.init_db()
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id FROM formulations ORDER BY id").fetchall()
    conn.close()
    for row in rows:
        rec = store.get(row["id"])
        if rec:
            yield rec


if __name__ == "__main__":
    sys.exit(main())
