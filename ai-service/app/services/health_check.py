"""Deep dependency checks for /health and /health/ready."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.config import get_settings
from app.formulation.store import DB_PATH
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


def check_sqlite() -> DependencyStatus:
    try:
        if not DB_PATH.is_file():
            return DependencyStatus(name="sqlite", ok=False, detail="formulations.db missing")
        conn = sqlite3.connect(DB_PATH)
        n = conn.execute("SELECT COUNT(*) FROM formulations").fetchone()[0]
        conn.close()
        if n < 1:
            return DependencyStatus(name="sqlite", ok=False, detail="no formulations")
        return DependencyStatus(name="sqlite", ok=True, detail=f"{n} formulations")
    except Exception as exc:
        return DependencyStatus(name="sqlite", ok=False, detail=str(exc))


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


def readiness_report(*, include_embed: bool = False) -> ReadinessReport:
    deps = [check_qdrant(), check_sqlite()]
    if include_embed:
        deps.append(check_embed_model())
    ok = all(d.ok for d in deps)
    return ReadinessReport(ok=ok, dependencies=deps)
