"""Chat entrypoint: delegates to router with fallback orchestration."""
from __future__ import annotations

import logging

from app.reasoning.router import route_chat
from app.schemas import ChatTurnRequest, ChatTurnResponse


logger = logging.getLogger(__name__)


def run_chat_pipeline(payload: ChatTurnRequest) -> ChatTurnResponse:
    routed = route_chat(payload)
    logger.info(
        "Chat route=%s llm_used=%s fallback=%s confidence=%s",
        routed.response.route,
        routed.llm_used,
        routed.fallback_stage,
        routed.response.search_confidence,
    )
    return routed.response
