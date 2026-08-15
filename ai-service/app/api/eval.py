from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.eval.feedback_log import append_feedback, feedback_stats


router = APIRouter(prefix="/eval", tags=["eval"])


class FeedbackRequest(BaseModel):
    message_id: str
    thread_id: str | None = None
    rating: int = Field(..., ge=-1, le=1)
    user_message: str | None = None
    assistant_message: str | None = None
    route: str | None = None


@router.post("/feedback")
def record_feedback(body: FeedbackRequest) -> dict:
    append_feedback(body.model_dump())
    return {"ok": True}


@router.get("/feedback/stats")
def feedback_summary() -> dict:
    return feedback_stats()
