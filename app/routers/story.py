"""Story chapter endpoints — read state, mark cutscene seen.

Combat itself stays in /battles. Story is just narrative framing on top.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.account_level import (
    chapter_by_code,
    chapter_status_for_account,
    has_seen,
    mark_seen,
)
from app.db import get_db
from app.deps import get_current_account
from app.models import Account

router = APIRouter(prefix="/story", tags=["story"])


class StoryChaptersOut(BaseModel):
    account_level: int
    chapters: list[dict]


@router.get("", response_model=StoryChaptersOut)
def list_chapters(
    account: Annotated[Account, Depends(get_current_account)],
) -> StoryChaptersOut:
    return StoryChaptersOut(
        account_level=int(account.account_level or 1),
        chapters=chapter_status_for_account(account),
    )


class CutsceneSeenIn(BaseModel):
    chapter_code: str
    stage_code: str
    beat: str  # "intro" | "outro"


@router.post("/cutscene-seen", status_code=status.HTTP_204_NO_CONTENT)
def cutscene_seen(
    body: CutsceneSeenIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if chapter_by_code(body.chapter_code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chapter not found")
    if body.beat not in ("intro", "outro"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "beat must be 'intro' or 'outro'")
    key = f"{body.chapter_code}:{body.stage_code}:{body.beat}"
    mark_seen(account, key)
    db.commit()
    return None
