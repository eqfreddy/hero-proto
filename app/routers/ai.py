"""Battle narration via Claude — streams an IT-flavored incident postmortem."""
import json
import logging
from typing import Annotated, AsyncIterator

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.types import Receive, Scope, Send

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, Battle

router = APIRouter(prefix="/battles", tags=["ai"])

_log = logging.getLogger("ai")

_SYSTEM = (
    "You are the IT Operations Postmortem Bot. "
    "When given a battle summary, narrate the outcome as a dry internal IT incident report. "
    "Use corporate IT jargon, passive-aggressive tone, and understated Gen X humor. "
    "Keep it to exactly 2-3 sentences. No markdown. No bullet points. Plain text only."
)


class _DirectStreamingResponse(StreamingResponse):
    """StreamingResponse that skips Starlette's task-group disconnect detection.

    Starlette 1.0.0 wraps streaming in a task group and calls the middleware-
    supplied receive() to detect client disconnects. BaseHTTPMiddleware's receive
    raises StopAsyncIteration immediately for GET requests (no body), which cancels
    the stream task before any bytes are sent. This subclass overrides __call__ to
    send the response linearly without invoking receive at all.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        async for chunk in self.body_iterator:
            if not isinstance(chunk, bytes):
                chunk = chunk.encode(self.charset)
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})


def _build_prompt(battle: Battle) -> str:
    try:
        participants = json.loads(battle.participants_json or "[]")
    except json.JSONDecodeError:
        participants = []

    try:
        log = json.loads(battle.log_json or "[]")
    except json.JSONDecodeError:
        log = []

    heroes = [p for p in participants if p.get("side") == "player"]
    enemies = [p for p in participants if p.get("side") == "enemy"]

    hero_names = ", ".join(p.get("name", "Unknown") for p in heroes) or "Unknown team"
    enemy_names = ", ".join(p.get("name", "Unknown") for p in enemies) or "Unknown opposition"

    notable = []
    for entry in log:
        msg = entry.get("msg", "")
        if "defeated" in msg.lower() or "special" in msg.lower() or "critical" in msg.lower():
            notable.append(msg)
        if len(notable) >= 4:
            break

    notable_str = " | ".join(notable) if notable else "Combat proceeded without incident."

    outcome = battle.outcome.value if hasattr(battle.outcome, "value") else str(battle.outcome)

    return (
        f"Incident ID: BATTLE-{battle.id}\n"
        f"Stage: {battle.stage_id}\n"
        f"Outcome: {outcome}\n"
        f"Responding team: {hero_names}\n"
        f"Threat actors: {enemy_names}\n"
        f"Notable events: {notable_str}\n"
        f"First clear: {battle.first_clear}"
    )


async def _stream_narration(prompt: str) -> AsyncIterator[str]:
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        async with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=256,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        _log.exception("narration stream error")
        yield f"data: [ERROR] {type(e).__name__}: {e}\n\n"


@router.get("/{battle_id}/narration")
async def get_battle_narration(
    battle_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    if not settings.anthropic_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI narration not configured")

    battle = db.scalar(select(Battle).where(Battle.id == battle_id))
    if battle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Battle not found")
    if battle.account_id != account.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your battle")

    prompt = _build_prompt(battle)

    return _DirectStreamingResponse(
        _stream_narration(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
