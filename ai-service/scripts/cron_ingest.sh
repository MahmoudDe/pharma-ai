#!/usr/bin/env bash
# Weekly ingest: re-index PDFs when docs change (or force with INGEST_FORCE=1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/python ]]; then
  PY=".venv/bin/python"
else
  PY=python3
fi

FORCE=""
if [[ "${INGEST_FORCE:-0}" == "1" ]]; then
  FORCE="--force"
fi

echo "[cron-ingest] $(date -Iseconds) starting"
docker compose up -d qdrant
"$PY" -m app.ingestion.run_ingest $FORCE
echo "[cron-ingest] $(date -Iseconds) done"
