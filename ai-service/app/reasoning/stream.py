"""Server-Sent Events for streaming chat turns."""
from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Iterator

from app.reasoning.router import RoutedResponse, route_chat
from app.schemas import ChatTurnRequest, ChatTurnResponse


logger = logging.getLogger(__name__)


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def iter_chat_sse(payload: ChatTurnRequest) -> Iterator[str]:
    """Yield SSE frames while the LLM streams; finish with a done payload."""
    events: queue.Queue[tuple[str, object]] = queue.Queue()
    result: list[RoutedResponse] = []
    error: list[str] = []

    def on_token(delta: str) -> None:
        events.put(("token", delta))

    def worker() -> None:
        try:
            result.append(route_chat(payload, on_token=on_token))
        except Exception as exc:
            logger.exception("Stream worker failed")
            error.append(str(exc))
            events.put(("error", str(exc)))
        finally:
            events.put(("finished", None))

    threading.Thread(target=worker, daemon=True).start()

    while True:
        try:
            kind, data = events.get(timeout=180)
        except queue.Empty:
            continue

        if kind == "token":
            yield _sse("token", {"delta": data})
        elif kind == "error":
            return
        elif kind == "finished":
            break

    if error:
        return

    if not result:
        yield _sse("error", {"message": "Chat pipeline returned no result."})
        return

    routed = result[0]
    yield _sse("done", routed.response.model_dump(mode="json"))
    logger.info(
        "Stream complete route=%s llm=%s",
        routed.response.route,
        routed.llm_used,
    )


def parse_done_event(data: str) -> ChatTurnResponse:
    return ChatTurnResponse.model_validate_json(data)
