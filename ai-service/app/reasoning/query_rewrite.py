"""Conversation-aware query rewriting before retrieval."""
from __future__ import annotations

import json
import logging
import re

from app.config import get_settings
from app.reasoning.llm import _client
from app.schemas import ChatHistoryMessage


logger = logging.getLogger(__name__)

_FOLLOWUP_START = re.compile(
    r"^(make it|make that|can you|could you|also|what about|how about|"
    r"instead|without|with no|sulfate[- ]?free|compare|the same|"
    r"that one|those|this one|version)\b",
    re.I,
)
_REFERENCE = re.compile(
    r"\b(that|those|it|this|them|same|previous|above|earlier|second|first)\b",
    re.I,
)


def _recent_user_message(history: list[ChatHistoryMessage]) -> str | None:
    for msg in reversed(history):
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip()[:400]
    return None


def needs_rewrite(query: str, history: list[ChatHistoryMessage]) -> bool:
    if not history:
        return False
    q = query.strip()
    if not q:
        return False
    word_count = len(q.split())
    if word_count <= 6:
        return True
    if word_count <= 12 and (_FOLLOWUP_START.search(q) or _REFERENCE.search(q)):
        return True
    return False


def heuristic_rewrite(query: str, history: list[ChatHistoryMessage]) -> str:
    last_user = _recent_user_message(history)
    if not last_user:
        return query
    follow_up = query.strip()
    if follow_up.lower() == last_user.lower():
        return follow_up
    return f"{last_user} — {follow_up}"


def llm_rewrite(query: str, history: list[ChatHistoryMessage]) -> str:
    settings = get_settings()
    client = _client()
    recent = history[-settings.chat_history_max_messages :]
    lines: list[str] = []
    for msg in recent:
        role = "User" if msg.role == "user" else "Assistant"
        text = msg.content.strip()[:500]
        if text:
            lines.append(f"{role}: {text}")

    prompt = (
        "Rewrite the latest user message into a standalone cosmetic formulation search query "
        "that preserves product type and constraints from the conversation. "
        "Return JSON: {\"query\": \"...\"}. One short sentence, no explanation."
    )
    completion = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    "Conversation:\n"
                    + "\n".join(lines)
                    + f"\n\nLatest user message to rewrite: {query}"
                ),
            },
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)
    rewritten = str(data.get("query", "")).strip()
    return rewritten or heuristic_rewrite(query, history)


def rewrite_search_query(
    query: str,
    history: list[ChatHistoryMessage] | None,
) -> tuple[str, bool]:
    """Return (query for retrieval/classification, was_rewritten)."""
    history = history or []
    if not needs_rewrite(query, history):
        return query, False

    settings = get_settings()
    if settings.enable_conversation_rewrite and settings.llm_api_key:
        try:
            return llm_rewrite(query, history), True
        except Exception:
            logger.exception("LLM conversation rewrite failed; using heuristic")

    return heuristic_rewrite(query, history), True
