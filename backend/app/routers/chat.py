import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import chat_service

router = APIRouter()

# In-memory per-IP rate limit. Good enough for a single-instance free-tier
# deploy (Render's WEB_CONCURRENCY=1 here) — resets on redeploy/restart,
# and wouldn't hold up across multiple instances, but it's a real bound on
# API spend from anonymous visitors without adding a dependency or forcing
# a login just to use the chat widget.
_RATE_LIMIT = 20
_RATE_WINDOW_SECONDS = 3600
_hits: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    recent = [t for t in _hits[client_ip] if now - t < _RATE_WINDOW_SECONDS]
    if len(recent) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many messages — try again in a bit.")
    recent.append(now)
    _hits[client_ip] = recent


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)


@router.post("/message")
async def send_message(request: ChatRequest, http_request: Request):
    client_ip = http_request.client.host if http_request.client else "unknown"
    _check_rate_limit(client_ip)

    try:
        reply = await chat_service.get_chat_response(
            [{"role": m.role, "content": m.content} for m in request.messages]
        )
        return {"reply": reply}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat assistant failed: {exc}") from exc
