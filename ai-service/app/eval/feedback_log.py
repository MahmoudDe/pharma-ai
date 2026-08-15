from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import PROJECT_ROOT


_LOG_PATH = PROJECT_ROOT / "data" / "feedback_log.jsonl"


def append_feedback(entry: dict) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        **entry,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    with _LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def feedback_stats() -> dict:
    if not _LOG_PATH.is_file():
        return {"count": 0, "positive": 0, "negative": 0}
    positive = 0
    negative = 0
    with _LOG_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rating = row.get("rating")
            if rating == 1:
                positive += 1
            elif rating == -1:
                negative += 1
    return {
        "count": positive + negative,
        "positive": positive,
        "negative": negative,
        "path": str(_LOG_PATH),
    }
