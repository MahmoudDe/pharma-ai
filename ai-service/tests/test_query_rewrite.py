from __future__ import annotations

from app.reasoning.query_rewrite import (
    heuristic_rewrite,
    needs_rewrite,
    rewrite_search_query,
)
from app.schemas import ChatHistoryMessage


def _history(*pairs: tuple[str, str]) -> list[ChatHistoryMessage]:
    out: list[ChatHistoryMessage] = []
    for user, assistant in pairs:
        out.append(ChatHistoryMessage(role="user", content=user))
        out.append(ChatHistoryMessage(role="assistant", content=assistant))
    return out


def test_needs_rewrite_short_follow_up():
    history = _history(
        ("Give me a baby shampoo formula", "Here is a mild baby shampoo…"),
    )
    assert needs_rewrite("make it sulfate-free", history)


def test_needs_rewrite_false_without_history():
    assert not needs_rewrite("make it sulfate-free", [])


def test_needs_rewrite_false_for_meta_and_reactions():
    history = _history(
        ("Give me a sulfate-free shampoo", "Here is a sulfate-free shampoo…"),
    )
    assert not needs_rewrite("who are you", history)
    assert not needs_rewrite("wow", history)
    assert not needs_rewrite("واو", history)


def test_needs_rewrite_false_for_new_product_topic():
    history = _history(
        ("Give me a baby shampoo formula", "Baby shampoo with CAPB…"),
    )
    assert not needs_rewrite("hand cream", history)
    assert not needs_rewrite("give me a hand cream formula", history)


def test_needs_rewrite_false_for_standalone_short_product():
    history = _history(
        ("Give me a baby shampoo formula", "Baby shampoo with CAPB…"),
    )
    # Same family but a new standalone lookup — do not glue onto prior baby context.
    assert not needs_rewrite("shampoo", history)


def test_heuristic_rewrite_combines_context():
    history = _history(
        ("Give me a baby shampoo formula", "Baby shampoo with CAPB…"),
    )
    out = heuristic_rewrite("make it sulfate-free", history)
    assert "baby shampoo" in out.lower()
    assert "sulfate-free" in out.lower()


def test_rewrite_search_query_without_history():
    q, rewritten = rewrite_search_query("baby shampoo formula", None)
    assert q == "baby shampoo formula"
    assert rewritten is False


def test_rewrite_search_query_skips_topic_change():
    history = _history(
        ("Give me a baby shampoo formula", "Baby shampoo…"),
    )
    q, rewritten = rewrite_search_query("hand cream", history)
    assert q == "hand cream"
    assert rewritten is False
