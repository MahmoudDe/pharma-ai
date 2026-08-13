"""Tests for conversation-aware query rewriting."""
from __future__ import annotations

from app.reasoning.query_rewrite import (
    heuristic_rewrite,
    needs_rewrite,
    rewrite_search_query,
)
from app.schemas import ChatHistoryMessage


def test_needs_rewrite_short_follow_up():
    history = [
        ChatHistoryMessage(role="user", content="Give me a baby shampoo formula"),
        ChatHistoryMessage(role="assistant", content="Here is a mild baby shampoo…"),
    ]
    assert needs_rewrite("make it sulfate-free", history)


def test_needs_rewrite_false_without_history():
    assert not needs_rewrite("make it sulfate-free", [])


def test_heuristic_rewrite_combines_context():
    history = [
        ChatHistoryMessage(role="user", content="Give me a baby shampoo formula"),
        ChatHistoryMessage(role="assistant", content="Baby shampoo with CAPB…"),
    ]
    out = heuristic_rewrite("make it sulfate-free", history)
    assert "baby shampoo" in out.lower()
    assert "sulfate-free" in out.lower()


def test_rewrite_search_query_without_history():
    q, rewritten = rewrite_search_query("baby shampoo formula", None)
    assert q == "baby shampoo formula"
    assert rewritten is False
