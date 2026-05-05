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
from app.models import Account, Faction, utcnow

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


_VALID_ALIGNMENTS = {Faction.RESISTANCE, Faction.CORP_GREED}


class AlignmentChoiceIn(BaseModel):
    alignment: str  # "RESISTANCE" | "CORP_GREED"


class AlignmentChoiceOut(BaseModel):
    faction: str
    alignment_chosen_at: str


@router.post("/alignment", response_model=AlignmentChoiceOut, status_code=status.HTTP_200_OK)
def choose_alignment(
    body: AlignmentChoiceIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> AlignmentChoiceOut:
    """One-time alignment fork at level 50.

    Requirements:
    - account_level >= 50
    - current faction is EXILE
    - alignment_chosen_at is None (idempotency guard)
    - alignment must be RESISTANCE or CORP_GREED

    Returns 409 if already aligned, 403 if below level 50.
    """
    try:
        chosen = Faction(body.alignment)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"alignment must be one of: {', '.join(f.value for f in _VALID_ALIGNMENTS)}",
        )
    if chosen not in _VALID_ALIGNMENTS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"alignment must be RESISTANCE or CORP_GREED",
        )

    if int(account.account_level or 1) < 50:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "alignment fork unlocks at account level 50",
        )

    current_faction = account.faction if isinstance(account.faction, Faction) else Faction(account.faction or "EXILE")
    if current_faction != Faction.EXILE or account.alignment_chosen_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"alignment already set to {account.faction}",
        )

    account.faction = chosen
    account.alignment_chosen_at = utcnow()

    # Universal reward — every player who reaches the fork gets the LEGS
    # piece of the Veteran IT armor set, regardless of which side they pick.
    from app.named_gear import grant_named_gear, by_code as named_by_code
    legs_granted = grant_named_gear(db, account, "cargo_pants_of_many_tabs")
    db.commit()

    from app.notifications import notify as _notify
    body_lines = ["Your path is set. The story continues in Chapter 4."]
    if legs_granted:
        spec = named_by_code("cargo_pants_of_many_tabs")
        if spec is not None:
            body_lines.append(f"Reward: {spec.icon} {spec.name}")
    _notify(
        db, account,
        kind="alignment_chosen",
        title=f"Alignment chosen: {chosen.value}",
        body=" ".join(body_lines),
        link="/app/story",
        icon="🌀",
    )

    return AlignmentChoiceOut(
        faction=chosen.value,
        alignment_chosen_at=account.alignment_chosen_at.isoformat(),
    )
