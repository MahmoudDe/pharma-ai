from __future__ import annotations

import json
import logging

from app.formulation.schemas import IngredientLine
from app.config import get_settings
from app.reasoning import llm as llm_module


logger = logging.getLogger(__name__)


def llm_extract_ingredients(block_text: str, name: str) -> list[IngredientLine]:
    settings = get_settings()
    if not settings.llm_api_key:
        return []

    client = llm_module._client()
    prompt = (
        f"Extract cosmetic formulation ingredients from this text for '{name}'. "
        "Return JSON array: [{\"raw_name\": str, \"amount\": number|null, \"unit\": str|null, \"phase\": str|null}]"
    )
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Return only valid JSON array."},
                {"role": "user", "content": f"{prompt}\n\n{block_text[:4000]}"},
            ],
        )
        raw = response.choices[0].message.content or "[]"
        data = json.loads(raw)
        return [
            IngredientLine(
                raw_name=str(item.get("raw_name", "")),
                normalized_name=str(item.get("raw_name", "")).lower(),
                amount=item.get("amount"),
                unit=item.get("unit"),
                phase=item.get("phase"),
            )
            for item in data
            if item.get("raw_name")
        ]
    except Exception as exc:
        logger.warning("LLM formula extraction failed: %s", exc)
        return []
