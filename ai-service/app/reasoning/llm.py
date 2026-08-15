"""OpenAI chat-completions wrapper with JSON-object response forcing."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from collections.abc import Callable
from typing import Literal

from openai import OpenAI

from app.config import get_settings


logger = logging.getLogger(__name__)


Confidence = Literal["low", "medium", "high"]
_VALID_CONFIDENCE: set[str] = {"low", "medium", "high"}
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


@dataclass(slots=True)
class FormulaLine:
    ingredient: str
    percentage: str | None
    source_index: int


@dataclass(slots=True)
class LLMCitation:
    source_index: int
    quote: str
    confidence: Confidence


@dataclass(slots=True)
class LLMResponse:
    answer: str
    citations: list[LLMCitation]
    formula_lines: list[FormulaLine] = field(default_factory=list)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError(
            "LLM_API_KEY is empty. Set it in ai-service/.env (an OpenRouter key from "
            "https://openrouter.ai/keys works, as does an OpenAI key if you point "
            "LLM_BASE_URL at https://api.openai.com/v1)."
        )
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )


def _coerce_confidence(value: object) -> Confidence:
    if isinstance(value, str) and value.lower() in _VALID_CONFIDENCE:
        return value.lower()  # type: ignore[return-value]
    return "low"


def _parse_formula_lines(raw: object) -> list[FormulaLine]:
    if not isinstance(raw, list):
        return []
    lines: list[FormulaLine] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ingredient = str(item.get("ingredient", "")).strip()
        if not ingredient:
            continue
        try:
            source_index = int(item.get("source_index", 0))
        except (TypeError, ValueError):
            continue
        pct = item.get("percentage")
        percentage = str(pct).strip() if pct is not None and str(pct).strip() else None
        lines.append(
            FormulaLine(
                ingredient=ingredient,
                percentage=percentage,
                source_index=source_index,
            )
        )
    return lines


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


def _looks_like_json_object(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{")


def _parse(raw: str) -> LLMResponse:
    """Parse model output. Unwraps JSON {answer, citations, formula_lines} when present."""
    text = _strip_code_fences(raw)
    if not text:
        return LLMResponse(answer="", citations=[])

    data: object | None = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Model sometimes emits prose then a JSON blob, or a truncated object.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                data = None

    if not isinstance(data, dict) or "answer" not in data:
        if data is not None and not isinstance(data, dict):
            logger.warning("LLM returned non-object JSON; falling back to raw text")
        elif _looks_like_json_object(text):
            logger.warning("LLM returned JSON without answer field; falling back to raw text")
        return LLMResponse(answer=text.strip(), citations=[])

    answer = str(data.get("answer", "")).strip()
    citations_raw = data.get("citations") or []
    citations: list[LLMCitation] = []
    if isinstance(citations_raw, list):
        for item in citations_raw:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("source_index"))
            except (TypeError, ValueError):
                continue
            quote = str(item.get("quote", "")).strip()
            if not quote:
                continue
            citations.append(
                LLMCitation(
                    source_index=idx,
                    quote=quote,
                    confidence=_coerce_confidence(item.get("confidence")),
                )
            )

    formula_lines = _parse_formula_lines(data.get("formula_lines"))
    return LLMResponse(answer=answer, citations=citations, formula_lines=formula_lines)


def reason(*, system_prompt: str, context_block: str, user_message: str) -> LLMResponse:
    settings = get_settings()
    client = _client()

    user_content = f"{context_block}\n\nUSER QUESTION:\n{user_message}"

    logger.info("Calling LLM model=%s, ctx_chars=%d", settings.llm_model, len(context_block))
    completion = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    raw = completion.choices[0].message.content or "{}"
    return _parse(raw)


def reason_stream(
    *,
    system_prompt: str,
    context_block: str,
    user_message: str,
    on_token: Callable[[str], None],
) -> LLMResponse:
    """Stream answer prose to the client; unwrap JSON if the model still emits it."""
    settings = get_settings()
    client = _client()
    user_content = f"{context_block}\n\nUSER QUESTION:\n{user_message}"

    logger.info(
        "Streaming LLM model=%s, ctx_chars=%d",
        settings.llm_model,
        len(context_block),
    )
    completion = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    parts: list[str] = []
    live = True  # False once we detect a JSON object — buffer instead of showing raw keys.

    for event in completion:
        delta = event.choices[0].delta.content or ""
        if not delta:
            continue
        parts.append(delta)
        so_far = "".join(parts)
        if live and _looks_like_json_object(so_far):
            live = False
            continue
        if live:
            on_token(delta)

    raw = "".join(parts).strip()
    parsed = _parse(raw)
    answer = parsed.answer.strip() or (
        "I could not synthesise an answer from the sources."
    )

    # JSON was buffered: flush the clean answer once so the UI is not empty mid-stream.
    if not live:
        on_token(answer)

    return LLMResponse(
        answer=answer,
        citations=parsed.citations,
        formula_lines=parsed.formula_lines,
    )
