from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.daily import ensure_today
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, DailyQuest, DailyQuestStatus, utcnow
from app.schemas import DailyQuestOut

router = APIRouter(prefix="/daily", tags=["daily"])


@router.get("", response_model=list[DailyQuestOut])
def list_daily(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DailyQuest]:
    quests = ensure_today(db, account)
    # ensure_today may have added rows; commit so the client sees stable ids on repeat calls.
    db.commit()
    return sorted(quests, key=lambda q: q.id)


@router.post("/{quest_id}/claim", response_model=DailyQuestOut)
def claim(
    quest_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> DailyQuest:
    q = db.get(DailyQuest, quest_id)
    if q is None or q.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "daily quest not found")
    if q.status != DailyQuestStatus.COMPLETE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"quest not claimable (status={q.status})")
    account.gems += q.reward_gems
    account.coins += q.reward_coins
    account.shards += q.reward_shards
    q.status = DailyQuestStatus.CLAIMED
    q.claimed_at = utcnow()
    db.commit()
    db.refresh(q)
    return q
