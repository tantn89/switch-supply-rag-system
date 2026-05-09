"""POST /chat — streaming RAG response over Server-Sent Events."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.streaming.sse_formatter import sse

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None  # reserved for future multi-turn support


@router.post("")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    engine = request.app.state.engine

    async def event_stream():
        try:
            async for ev in engine.stream_answer(req.message):
                yield sse(ev["event"], ev["data"])
        except Exception as exc:  # noqa: BLE001 — surface failure to client
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering on Render/Cloudflare
            "Connection": "keep-alive",
        },
    )


@router.post("/sync")
def chat_sync(req: ChatRequest, request: Request):
    """Non-streaming variant for tests / batch evaluation."""
    engine = request.app.state.engine
    return engine.answer(req.message).model_dump()
