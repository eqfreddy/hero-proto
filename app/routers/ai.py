"""Battle narration via Claude — streams an IT-flavored incident postmortem."""
import json
import logging
from typing import Annotated, AsyncIterator

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

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

    # Pick a few notable events from the log (KOs, specials)
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
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    async with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            # SSE format: data: <chunk>\n\n
            yield f"data: {text}\n\n"
    yield "data: [DONE]\n\n"


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

    return StreamingResponse(
        _stream_narration(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
