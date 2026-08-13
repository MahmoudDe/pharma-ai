"""Tests for conversation history in LLM context formatting."""
from __future__ import annotations

from app.reasoning.prompt import format_conversation_history
from app.schemas import ChatHistoryMessage


def test_format_conversation_history_empty():
    assert format_conversation_history([]) == ""


def test_format_conversation_history_includes_roles():
    history = [
        ChatHistoryMessage(role="user", content="Baby shampoo formula"),
        ChatHistoryMessage(role="assistant", content="Here is a mild formula."),
    ]
    block = format_conversation_history(history)
    assert "CONVERSATION HISTORY" in block
    assert "User: Baby shampoo" in block
    assert "Assistant: Here is a mild" in block
