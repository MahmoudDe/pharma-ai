from __future__ import annotations

import json
import logging
import re

from app.config import get_settings
from app.reasoning.llm import _client
from app.retrieval.intent import parse_query_intent
from app.schemas import ChatHistoryMessage


logger = logging.getLogger(__name__)

_FOLLOWUP_START = re.compile(
    r"^(make it|make that|can you make|could you make|also|what about|how about|"
    r"instead|without|with no|sulfate[- ]?free|compare|the same|"
    r"that one|those|this one|version|add |remove |swap |replace )\b",
    re.I,
)
_REFERENCE = re.compile(
    r"\b(that|those|it|this|them|same|previous|above|earlier|second|first)\b",
    re.I,
)
_CONSTRAINT = re.compile(
    r"\b(sulfate[- ]?free|paraben[- ]?free|fragrance[- ]?free|silicone[- ]?free|"
    r"without|with no|no\s+\w+|cheaper|milder|gentler|natural|organic|"
    r"for\s+(dry|oily|sensitive|normal)\s+skin)\b",
    re.I,
)
# Greetings, reactions, meta questions — never glue onto the previous formula search.
_META = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|cool|wow|nice|great|yes|no|yep|nope|"
    r"who are you|what are you|help|test|مرحبا|شكرا|واو|تمام|حسنا|اه|لا)[\s!.?]*$",
    re.I,
)


def _recent_user_message(history: list[ChatHistoryMessage]) -> str | None:
    for msg in reversed(history):
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip()[:400]
    return None


def _product_types(text: str) -> set[str]:
    return set(parse_query_intent(text).product_types)


def needs_rewrite(query: str, history: list[ChatHistoryMessage]) -> bool:
    """Only rewrite clear follow-ups — never force a new topic onto the prior search."""
    if not history:
        return False
    q = query.strip()
    if not q:
        return False
    if _META.match(q):
        return False

    word_count = len(q.split())
    last_user = _recent_user_message(history)
    cur_types = _product_types(q)
    prev_types = _product_types(last_user) if last_user else set()

    # Explicit new product family → standalone lookup, do not inherit prior topic.
    if cur_types and prev_types and cur_types.isdisjoint(prev_types):
        return False

    if _FOLLOWUP_START.search(q):
        return True
    if word_count <= 12 and _REFERENCE.search(q) and not (cur_types and not prev_types):
        return True
    # Short constraint-only refinements ("sulfate-free", "without SLS")
    if word_count <= 8 and _CONSTRAINT.search(q) and not cur_types:
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
        "Rewrite the latest user message into a standalone cosmetic formulation search query.\n"
        "Rules:\n"
        "- If the latest message is a follow-up or refinement of the previous request, "
        "merge product type and constraints from the conversation.\n"
        "- If the latest message is a NEW product/topic, greeting, reaction, or unrelated "
        "question, return it UNCHANGED — do not force the previous product type.\n"
        'Return JSON: {"query": "..."}. One short sentence, no explanation.'
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


def _llm_stuck_on_prior_topic(
    original: str,
    rewritten: str,
    history: list[ChatHistoryMessage],
) -> bool:
    """Detect when the LLM glued a new/meta message onto the previous product search."""
    if rewritten.strip().lower() == original.strip().lower():
        return False
    # Clear refinements are supposed to inherit the prior product family.
    if (
        _FOLLOWUP_START.search(original)
        or _CONSTRAINT.search(original)
        or _REFERENCE.search(original)
    ):
        return False
    last_user = _recent_user_message(history)
    if not last_user:
        return False
    orig_types = _product_types(original)
    rew_types = _product_types(rewritten)
    prev_types = _product_types(last_user)
    # Original had no product cue but rewrite revived the prior product family.
    if not orig_types and prev_types and rew_types & prev_types:
        return True
    # Original asked for a different product family than the rewrite kept.
    if orig_types and prev_types and orig_types.isdisjoint(prev_types) and rew_types & prev_types:
        return True
    return False


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
            rewritten = llm_rewrite(query, history)
            if _llm_stuck_on_prior_topic(query, rewritten, history):
                logger.info(
                    "Discarding rewrite that stuck on prior topic: %r -> %r",
                    query[:80],
                    rewritten[:80],
                )
                return query, False
            return rewritten, True
        except Exception:
            logger.exception("LLM conversation rewrite failed; using heuristic")

    return heuristic_rewrite(query, history), True
