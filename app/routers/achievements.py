"""Achievement read endpoint. Catalog joined with caller's unlock state."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.achievements import unlock_progress
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


class AchievementSummaryOut(BaseModel):
    total: int
    unlocked: int
    items: list[AchievementOut]


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
    )
