"""CLI worker for ingest jobs (optional; API also runs jobs in background threads)."""
from __future__ import annotations

import argparse
import logging
import sys
import time

from app.ingestion.jobs import get_job, list_jobs, run_job


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Run queued ingest jobs")
    parser.add_argument("--job-id", default=None, help="Run a specific job id")
    parser.add_argument("--poll", action="store_true", help="Poll queued jobs until idle")
    args = parser.parse_args(argv)

    if args.job_id:
        run_job(args.job_id)
        job = get_job(args.job_id)
        if job and job.status == "failed":
            logger.error("Job failed: %s", job.error)
            return 1
        return 0

    if args.poll:
        while True:
            queued = [j for j in list_jobs(50) if j.status == "queued"]
            if not queued:
                time.sleep(2)
                continue
            for job in queued:
                logger.info("Running job %s", job.id)
                run_job(job.id)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
