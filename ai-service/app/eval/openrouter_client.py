from __future__ import annotations

import json
import logging
from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError(
            "LLM_API_KEY is required for OpenRouter eval. Set it in ai-service/.env"
        )
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def eval_model_name() -> str:
    settings = get_settings()
    return settings.eval_model or settings.llm_model


def chat_json(*, system: str, user: str, model: str | None = None) -> dict:
    """Call OpenRouter with JSON object response."""
    client = _client()
    model = model or eval_model_name()
    logger.info("OpenRouter eval call model=%s user_chars=%d", model, len(user))
    completion = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"data": data}
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenRouter returned non-JSON: {raw[:200]}") from exc
