import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.reasoning.pipeline import run_chat_pipeline
from app.reasoning.stream import iter_chat_sse
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


@router.post("/chat/stream")
def chat_stream(payload: ChatTurnRequest) -> StreamingResponse:
    try:
        return StreamingResponse(
            iter_chat_sse(payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as exc:
        logger.exception("Chat stream failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
