"""File-based ingest job queue."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.config import get_settings


JobStatus = Literal["queued", "running", "done", "failed"]

_lock = threading.Lock()
_worker_started = False


@dataclass
class IngestJob:
    id: str
    status: JobStatus
    force: bool = False
    sqlite_only: bool = False
    pdf_only: bool = False
    docs_dir: str | None = None
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _jobs_dir() -> Path:
    settings = get_settings()
    path = Path(settings.ingest_jobs_dir)
    if not path.is_absolute():
        from app.config import PROJECT_ROOT

        path = (PROJECT_ROOT / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(
    *,
    force: bool = False,
    sqlite_only: bool = False,
    pdf_only: bool = False,
    docs_dir: str | None = None,
) -> IngestJob:
    job = IngestJob(
        id=str(uuid.uuid4()),
        status="queued",
        force=force,
        sqlite_only=sqlite_only,
        pdf_only=pdf_only,
        docs_dir=docs_dir,
        created_at=_now(),
    )
    _job_path(job.id).write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
    return job


def get_job(job_id: str) -> IngestJob | None:
    path = _job_path(job_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return IngestJob(**data)


def list_jobs(limit: int = 20) -> list[IngestJob]:
    jobs_dir = _jobs_dir()
    paths = sorted(jobs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[IngestJob] = []
    for path in paths[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append(IngestJob(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _update_job(job: IngestJob) -> None:
    _job_path(job.id).write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")


def run_job(job_id: str) -> None:
    job = get_job(job_id)
    if job is None or job.status != "queued":
        return
    job.status = "running"
    job.started_at = _now()
    _update_job(job)
    try:
        from app.ingestion.run_ingest import main as ingest_main

        argv: list[str] = []
        if job.force:
            argv.append("--force")
        if job.sqlite_only:
            argv.append("--sqlite-only")
        if job.pdf_only:
            argv.append("--pdf-only")
        if job.docs_dir:
            argv.extend(["--docs", job.docs_dir])
        code = ingest_main(argv)
        if code != 0:
            raise RuntimeError(f"Ingest exited with code {code}")
        job.status = "done"
        job.result = {"exit_code": code}
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
    finally:
        job.finished_at = _now()
        _update_job(job)


def enqueue_and_start(
    *,
    force: bool = False,
    sqlite_only: bool = False,
    pdf_only: bool = False,
    docs_dir: str | None = None,
) -> IngestJob:
    job = create_job(
        force=force,
        sqlite_only=sqlite_only,
        pdf_only=pdf_only,
        docs_dir=docs_dir,
    )

    def _runner() -> None:
        run_job(job.id)

    thread = threading.Thread(target=_runner, name=f"ingest-{job.id[:8]}", daemon=True)
    thread.start()
    return job


def load_manifest() -> dict[str, dict]:
    from app.ingestion.run_ingest import MANIFEST_PATH, _load_manifest

    return _load_manifest()
