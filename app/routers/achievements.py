"""Achievement read endpoint. Catalog joined with caller's unlock state.

Phase 3 teaser: HARDCORE_ACHIEVEMENTS surfaces a separate locked-but-
visible tier. No real unlock predicates yet — these render as long-tail
chase goals to give players something to aim for once Hardcore mode
ships alongside the level-50 alignment fork.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.achievements import HARDCORE_ACHIEVEMENTS, unlock_progress
from app.db import get_db
from app.deps import get_current_account
from app.models import Account

router = APIRouter(prefix="/achievements", tags=["achievements"])


class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    reward: dict
    unlocked: bool
    unlocked_at: str
    # Phase 2 polish — progress numbers for "do X N times" achievements.
    # has_progress=False means binary (existence-style) and the UI
    # should hide the progress bar.
    progress_current: int = 0
    progress_target: int = 0
    has_progress: bool = False


class HardcoreTeaserOut(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    reward_preview: str


class AchievementSummaryOut(BaseModel):
    total: int
    unlocked: int
    items: list[AchievementOut]
    # Phase 3 teaser — locked-but-visible long-tail goals.
    hardcore: list[HardcoreTeaserOut] = []


@router.get("", response_model=AchievementSummaryOut)
def list_achievements(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> AchievementSummaryOut:
    items = unlock_progress(db, account)
    return AchievementSummaryOut(
        total=len(items),
        unlocked=sum(1 for i in items if i["unlocked"]),
        items=[AchievementOut(**i) for i in items],
        hardcore=[HardcoreTeaserOut(**h) for h in HARDCORE_ACHIEVEMENTS],
    )
