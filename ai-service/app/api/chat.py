import logging

from fastapi import APIRouter, HTTPException

from app.reasoning.pipeline import run_chat_pipeline
from app.schemas import ChatTurnRequest, ChatTurnResponse


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatTurnResponse)
def chat(payload: ChatTurnRequest) -> ChatTurnResponse:
    try:
        return run_chat_pipeline(payload)
    except Exception as exc:
        logger.exception("Chat pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
