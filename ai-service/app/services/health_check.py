from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.config import get_settings
from app.formulation.store import DB_PATH, count_formulations, get_store
from app.ingestion.index import collection_stats, get_client


@dataclass(slots=True)
class DependencyStatus:
    name: str
    ok: bool
    detail: str = ""


@dataclass(slots=True)
class ReadinessReport:
    ok: bool
    dependencies: list[DependencyStatus] = field(default_factory=list)


def check_qdrant() -> DependencyStatus:
    settings = get_settings()
    try:
        client = get_client()
        collections = {c.name for c in client.get_collections().collections}
        if settings.qdrant_collection not in collections:
            return DependencyStatus(
                name="qdrant",
                ok=False,
                detail=f"collection {settings.qdrant_collection!r} missing",
            )
        stats = collection_stats()
        points = int(stats.get("points_count") or 0)
        if points < 1:
            return DependencyStatus(name="qdrant", ok=False, detail="collection empty")
        return DependencyStatus(name="qdrant", ok=True, detail=f"{points} points")
    except Exception as exc:
        return DependencyStatus(name="qdrant", ok=False, detail=str(exc))


def check_formulation_store() -> DependencyStatus:
    settings = get_settings()
    backend = settings.formulation_store
    try:
        if backend == "postgres":
            if not settings.database_url:
                return DependencyStatus(
                    name="formulations",
                    ok=False,
                    detail="DATABASE_URL missing for postgres store",
                )
            n = count_formulations()
            if n < 1:
                return DependencyStatus(
                    name="formulations",
                    ok=False,
                    detail="postgres: no formulations",
                )
            return DependencyStatus(
                name="formulations",
                ok=True,
                detail=f"postgres: {n} formulations",
            )

        if not DB_PATH.is_file():
            return DependencyStatus(name="formulations", ok=False, detail="formulations.db missing")
        conn = sqlite3.connect(DB_PATH)
        n = conn.execute("SELECT COUNT(*) FROM formulations").fetchone()[0]
        conn.close()
        if n < 1:
            return DependencyStatus(name="formulations", ok=False, detail="no formulations")
        return DependencyStatus(name="formulations", ok=True, detail=f"sqlite: {n} formulations")
    except Exception as exc:
        return DependencyStatus(name="formulations", ok=False, detail=str(exc))


def check_sqlite() -> DependencyStatus:
    """Backward-compatible alias used by older callers."""
    return check_formulation_store()


def check_embed_model() -> DependencyStatus:
    settings = get_settings()
    try:
        from app.ingestion.embed import embed_query

        vec = embed_query("health check")
        if len(vec) != settings.embed_dim:
            return DependencyStatus(
                name="embed",
                ok=False,
                detail=f"dim {len(vec)} != {settings.embed_dim}",
            )
        return DependencyStatus(name="embed", ok=True, detail=settings.embed_model)
    except Exception as exc:
        return DependencyStatus(name="embed", ok=False, detail=str(exc))


def check_bm25() -> DependencyStatus:
    try:
        from app.retrieval.bm25_index import get_bm25_index

        index = get_bm25_index()
        n = len(index.records)
        if n < 1:
            return DependencyStatus(name="bm25", ok=False, detail="index empty")
        return DependencyStatus(name="bm25", ok=True, detail=f"{n} documents")
    except Exception as exc:
        return DependencyStatus(name="bm25", ok=False, detail=str(exc))


def readiness_report(*, include_embed: bool = False, include_bm25: bool = True) -> ReadinessReport:
    deps = [check_qdrant(), check_formulation_store()]
    if include_bm25:
        deps.append(check_bm25())
    if include_embed:
        deps.append(check_embed_model())
    ok = all(d.ok for d in deps)
    return ReadinessReport(ok=ok, dependencies=deps)
