"""Cheap LLM query expansion for fallback search."""
from __future__ import annotations

import json
import logging
import re

from app.config import get_settings
from app.reasoning.llm import _client


logger = logging.getLogger(__name__)


def expand_query(query: str, *, max_phrases: int = 4) -> list[str]:
    """Return alternative search phrases; falls back to [query] on failure."""
    settings = get_settings()
    if not settings.enable_query_expansion or not settings.llm_api_key:
        return [query]

    try:
        client = _client()
        completion = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You expand cosmetic formulation search queries. "
                        "Return JSON: {\"phrases\": [\"...\", ...]} with 2-4 short synonym phrases "
                        "for the same product intent. No explanations."
                    ),
                },
                {"role": "user", "content": query},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        phrases = data.get("phrases") or data.get("alternatives") or []
        out = [query]
        for p in phrases:
            if isinstance(p, str) and p.strip() and p.strip().lower() != query.lower():
                out.append(p.strip())
            if len(out) >= max_phrases:
                break
        return out[:max_phrases] if len(out) > 1 else [query]
    except Exception:
        logger.exception("Query expansion failed")
        return [query]
