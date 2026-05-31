"""Build searchable corpus of ingredient names from formulations.db."""
from __future__ import annotations

import sqlite3
from functools import lru_cache

from app.formulation.normalize import normalize_ingredient_name
from app.formulation.store import DB_PATH


@lru_cache(maxsize=1)
def corpus_ingredient_names() -> list[tuple[str, str]]:
    """Return (display_raw, normalized) pairs from all extracted ingredients."""
    if not DB_PATH.is_file():
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT raw_name, normalized_name FROM ingredients"
    ).fetchall()
    conn.close()
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw, norm in rows:
        raw_s = (raw or "").strip()
        norm_s = (norm or normalize_ingredient_name(raw_s) or raw_s).strip().lower()
        if not norm_s or norm_s in seen:
            continue
        seen.add(norm_s)
        out.append((raw_s or norm_s, norm_s))
    return out
