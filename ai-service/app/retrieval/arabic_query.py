"""Translate Arabic chat queries to English for retrieval against English books."""
from __future__ import annotations

import json
import logging
import re

from app.config import get_settings
from app.reasoning.llm import _client


logger = logging.getLogger(__name__)
_ARABIC = re.compile(r"[\u0600-\u06FF]")


def query_has_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text))


def english_search_query(query: str) -> str:
    """Return English search text; passthrough if already Latin-only."""
    q = query.strip()
    if not q or not query_has_arabic(q):
        return q

    settings = get_settings()
    if not settings.llm_api_key:
        return q

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
                        "Translate cosmetic formulation questions from Arabic to concise English "
                        "search terms for textbook retrieval. Return JSON: "
                        '{"english_query": "...", "product_type": "shampoo|cream|..." or null}'
                    ),
                },
                {"role": "user", "content": q},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        eng = str(data.get("english_query", "")).strip()
        return eng or q
    except Exception:
        logger.exception("Arabic query translation failed")
        return q
