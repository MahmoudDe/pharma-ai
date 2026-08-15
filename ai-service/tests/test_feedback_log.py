from __future__ import annotations

from app.eval.feedback_log import append_feedback, feedback_stats


def test_append_feedback_counts(tmp_path, monkeypatch):
    log_path = tmp_path / "feedback_log.jsonl"
    monkeypatch.setattr("app.eval.feedback_log._LOG_PATH", log_path)
    append_feedback({"message_id": "m1", "rating": 1})
    append_feedback({"message_id": "m2", "rating": -1})
    stats = feedback_stats()
    assert stats["count"] == 2
    assert stats["positive"] == 1
    assert stats["negative"] == 1
