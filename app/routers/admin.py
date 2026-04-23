"""Admin endpoints. All gated on Account.is_admin."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    Account,
    Battle,
    HeroInstance,
    HeroTemplate,
    LiveOpsEvent,
    LiveOpsKind,
    utcnow,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- schemas -----------------------------------------------------------------


class AccountSummary(BaseModel):
    id: int
    email: str
    gems: int
    coins: int
    shards: int
    energy_stored: int
    arena_rating: int
    is_admin: bool
    is_banned: bool
    banned_reason: str
    created_at: datetime


class GrantIn(BaseModel):
    gems: int = 0
    coins: int = 0
    shards: int = 0
    energy: int = 0
    hero_template_code: str | None = None  # if set, grants 1 copy of that hero


class BanIn(BaseModel):
    reason: str = Field(max_length=256, default="violation of ToS")


class LiveOpsCreateIn(BaseModel):
    kind: LiveOpsKind
    name: str = Field(min_length=1, max_length=128)
    duration_hours: float = Field(gt=0, le=24 * 30)
    # Per-kind config — e.g. {"multiplier": 2.0} or {"chance_add": 0.3}
    payload: dict = Field(default_factory=dict)


class StatsOut(BaseModel):
    accounts_total: int
    accounts_banned: int
    heroes_total: int
    battles_last_24h: int
    active_liveops: int


# --- endpoints ---------------------------------------------------------------


def _summary(a: Account) -> AccountSummary:
    return AccountSummary(
        id=a.id,
        email=a.email,
        gems=a.gems,
        coins=a.coins,
        shards=a.shards,
        energy_stored=a.energy_stored,
        arena_rating=a.arena_rating,
        is_admin=a.is_admin,
        is_banned=a.is_banned,
        banned_reason=a.banned_reason,
        created_at=a.created_at,
    )


@router.get("/accounts", response_model=list[AccountSummary])
def list_accounts(
    q: str = "",
    limit: int = 50,
    _admin: Annotated[Account, Depends(get_current_admin)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[AccountSummary]:
    limit = max(1, min(200, limit))
    stmt = select(Account).order_by(Account.id.desc()).limit(limit)
    if q:
        stmt = select(Account).where(Account.email.ilike(f"%{q}%")).order_by(Account.id.desc()).limit(limit)
    return [_summary(a) for a in db.scalars(stmt)]


@router.get("/accounts/{account_id}", response_model=AccountSummary)
def get_account(
    account_id: int,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    return _summary(a)


@router.post("/accounts/{account_id}/grant", response_model=AccountSummary)
def grant(
    account_id: int,
    body: GrantIn,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.gems += body.gems
    a.coins += body.coins
    a.shards += body.shards
    if body.energy:
        a.energy_stored += body.energy
    if body.hero_template_code:
        tmpl = db.scalar(
            select(HeroTemplate).where(HeroTemplate.code == body.hero_template_code)
        )
        if tmpl is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown hero template code")
        db.add(HeroInstance(account_id=a.id, template_id=tmpl.id))
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/accounts/{account_id}/ban", response_model=AccountSummary)
def ban(
    account_id: int,
    body: BanIn,
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    if account_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot ban yourself")
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.is_banned = True
    a.banned_reason = body.reason.strip()
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/accounts/{account_id}/unban", response_model=AccountSummary)
def unban(
    account_id: int,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.is_banned = False
    a.banned_reason = ""
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/accounts/{account_id}/promote", response_model=AccountSummary)
def promote(
    account_id: int,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.is_admin = True
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/liveops", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_liveops(
    body: LiveOpsCreateIn,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    now = utcnow()
    event = LiveOpsEvent(
        kind=body.kind,
        name=body.name.strip(),
        starts_at=now,
        ends_at=now + timedelta(hours=body.duration_hours),
        payload_json=json.dumps(body.payload),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {
        "id": event.id,
        "kind": str(event.kind),
        "name": event.name,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
    }


@router.delete("/liveops/{event_id}", response_model=dict)
def cancel_liveops(
    event_id: int,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    event = db.get(LiveOpsEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    # End it now rather than hard-delete (preserves audit trail).
    event.ends_at = utcnow()
    db.commit()
    return {"cancelled_id": event_id}


@router.get("/stats", response_model=StatsOut)
def stats(
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> StatsOut:
    now = utcnow()
    day_ago = now - timedelta(hours=24)
    accounts_total = db.scalar(select(func.count(Account.id))) or 0
    accounts_banned = db.scalar(select(func.count(Account.id)).where(Account.is_banned.is_(True))) or 0
    heroes_total = db.scalar(select(func.count(HeroInstance.id))) or 0
    battles_24h = db.scalar(
        select(func.count(Battle.id)).where(Battle.created_at >= day_ago)
    ) or 0
    active_liveops = db.scalar(
        select(func.count(LiveOpsEvent.id)).where(
            LiveOpsEvent.starts_at <= now, LiveOpsEvent.ends_at > now
        )
    ) or 0
    return StatsOut(
        accounts_total=accounts_total,
        accounts_banned=accounts_banned,
        heroes_total=heroes_total,
        battles_last_24h=battles_24h,
        active_liveops=active_liveops,
    )
