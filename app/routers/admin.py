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
    AdminAuditLog,
    Battle,
    HeroInstance,
    HeroTemplate,
    LiveOpsEvent,
    LiveOpsKind,
    Purchase,
    PurchaseState,
    utcnow,
)
from app.store import apply_refund


def _audit(db: Session, actor: Account, action: str, target_id: int | None, **payload) -> None:
    db.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=action,
            target_id=target_id,
            payload_json=json.dumps(payload, default=str),
        )
    )

router = APIRouter(prefix="/admin", tags=["admin"])


# --- schemas -----------------------------------------------------------------


class AccountSummary(BaseModel):
    id: int
    email: str
    gems: int
    coins: int
    shards: int
    access_cards: int
    energy_stored: int
    arena_rating: int
    is_admin: bool
    is_banned: bool
    banned_reason: str
    banned_until: datetime | None
    created_at: datetime


class GrantIn(BaseModel):
    gems: int = 0
    coins: int = 0
    shards: int = 0
    access_cards: int = 0
    energy: int = 0
    hero_template_code: str | None = None  # if set, grants 1 copy of that hero


class BanIn(BaseModel):
    reason: str = Field(max_length=256, default="violation of ToS")
    # If set, ban auto-lifts once now >= banned_until (worker/deps handle the clear).
    duration_hours: float | None = Field(default=None, gt=0, le=24 * 365)


class LiveOpsCreateIn(BaseModel):
    kind: LiveOpsKind
    name: str = Field(min_length=1, max_length=128)
    duration_hours: float = Field(gt=0, le=24 * 30)
    # When the event becomes active. NULL/absent = starts immediately. Max 90
    # days out to keep the schedule sane — we're not planning year-ahead content here.
    starts_at: datetime | None = None
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
        access_cards=a.access_cards,
        energy_stored=a.energy_stored,
        arena_rating=a.arena_rating,
        is_admin=a.is_admin,
        is_banned=a.is_banned,
        banned_reason=a.banned_reason,
        banned_until=a.banned_until,
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
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.gems += body.gems
    a.coins += body.coins
    a.shards += body.shards
    a.access_cards += body.access_cards
    if body.energy:
        a.energy_stored += body.energy
    if body.hero_template_code:
        tmpl = db.scalar(
            select(HeroTemplate).where(HeroTemplate.code == body.hero_template_code)
        )
        if tmpl is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown hero template code")
        db.add(HeroInstance(account_id=a.id, template_id=tmpl.id))
    _audit(db, admin, "grant", a.id, **body.model_dump())
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
    a.banned_until = (
        utcnow() + timedelta(hours=body.duration_hours) if body.duration_hours else None
    )
    a.token_version = (a.token_version or 0) + 1  # invalidate any outstanding JWTs
    _audit(db, admin, "ban", a.id, reason=a.banned_reason, duration_hours=body.duration_hours)
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/accounts/{account_id}/unban", response_model=AccountSummary)
def unban(
    account_id: int,
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.is_banned = False
    a.banned_reason = ""
    a.banned_until = None
    _audit(db, admin, "unban", a.id)
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/accounts/{account_id}/promote", response_model=AccountSummary)
def promote(
    account_id: int,
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountSummary:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")
    a.is_admin = True
    _audit(db, admin, "promote", a.id)
    db.commit()
    db.refresh(a)
    return _summary(a)


@router.post("/liveops", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_liveops(
    body: LiveOpsCreateIn,
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    now = utcnow()
    starts_at = body.starts_at or now
    # Guard against silly schedules: no more than 90 days out, and don't accept events
    # scheduled to start in the past (beyond small clock skew).
    if starts_at < now - timedelta(minutes=5):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "starts_at is in the past — use now-or-later",
        )
    if starts_at > now + timedelta(days=90):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "starts_at cannot be more than 90 days in the future",
        )
    event = LiveOpsEvent(
        kind=body.kind,
        name=body.name.strip(),
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=body.duration_hours),
        payload_json=json.dumps(body.payload),
    )
    db.add(event)
    db.flush()  # need event.id for the audit entry
    _audit(db, admin, "liveops_create", event.id, kind=str(event.kind), name=event.name)
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
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    event = db.get(LiveOpsEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    # End it now rather than hard-delete (preserves audit trail).
    event.ends_at = utcnow()
    _audit(db, admin, "liveops_cancel", event_id)
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


class AuditEntry(BaseModel):
    id: int
    actor_id: int | None
    action: str
    target_id: int | None
    payload: dict
    created_at: datetime


@router.get("/audit", response_model=list[AuditEntry])
def audit(
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 100,
    action: str | None = None,
    target_id: int | None = None,
) -> list[AuditEntry]:
    limit = max(1, min(500, limit))
    stmt = select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AdminAuditLog.action == action)
    if target_id is not None:
        stmt = stmt.where(AdminAuditLog.target_id == target_id)
    rows = []
    for e in db.scalars(stmt):
        try:
            payload = json.loads(e.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {"_raw": e.payload_json}
        rows.append(
            AuditEntry(
                id=e.id,
                actor_id=e.actor_id,
                action=e.action,
                target_id=e.target_id,
                payload=payload,
                created_at=e.created_at,
            )
        )
    return rows


# --- Store admin -------------------------------------------------------------


class PurchaseAdminOut(BaseModel):
    id: int
    account_id: int
    sku: str
    title: str
    price_cents: int
    currency_code: str
    state: str
    processor: str
    processor_ref: str
    created_at: datetime
    completed_at: datetime | None
    refunded_at: datetime | None
    refund_reason: str


class RefundIn(BaseModel):
    reason: str = Field(default="", max_length=256)


@router.get("/purchases", response_model=list[PurchaseAdminOut])
def list_purchases(
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    account_id: int | None = None,
    state: str | None = None,
    limit: int = 100,
) -> list[PurchaseAdminOut]:
    """Paginated purchase log. Filter by account or state."""
    limit = max(1, min(500, limit))
    stmt = select(Purchase).order_by(Purchase.id.desc()).limit(limit)
    if account_id is not None:
        stmt = stmt.where(Purchase.account_id == account_id)
    if state:
        stmt = stmt.where(Purchase.state == state)
    return [
        PurchaseAdminOut(
            id=p.id, account_id=p.account_id, sku=p.sku, title=p.title_snapshot,
            price_cents=p.price_cents_paid, currency_code=p.currency_code,
            state=str(p.state), processor=p.processor, processor_ref=p.processor_ref,
            created_at=p.created_at, completed_at=p.completed_at,
            refunded_at=p.refunded_at, refund_reason=p.refund_reason,
        )
        for p in db.scalars(stmt)
    ]


@router.post("/purchases/{purchase_id}/refund", response_model=PurchaseAdminOut)
def refund_purchase(
    purchase_id: int,
    body: RefundIn,
    admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseAdminOut:
    """Reverse a completed purchase. Clawbacks paid currencies (clamped at zero) and
    marks the Purchase row REFUNDED. Hero items are *not* automatically removed — left
    for manual CS review."""
    p = db.get(Purchase, purchase_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "purchase not found")
    if p.state != PurchaseState.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot refund a {p.state} purchase",
        )
    acct = db.get(Account, p.account_id)
    if acct is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")

    reversed_ = apply_refund(db, acct, p, reason=body.reason)
    _audit(db, admin, "refund", p.id, account_id=p.account_id, reversed=reversed_, reason=body.reason)
    db.commit()
    db.refresh(p)
    return PurchaseAdminOut(
        id=p.id, account_id=p.account_id, sku=p.sku, title=p.title_snapshot,
        price_cents=p.price_cents_paid, currency_code=p.currency_code,
        state=str(p.state), processor=p.processor, processor_ref=p.processor_ref,
        created_at=p.created_at, completed_at=p.completed_at,
        refunded_at=p.refunded_at, refund_reason=p.refund_reason,
    )


# --- Analytics ---------------------------------------------------------------


class AnalyticsBucket(BaseModel):
    """Uniform shape for a "count over time window" metric."""
    last_24h: int
    last_7d: int
    total: int


class AnalyticsRevenueOut(BaseModel):
    total_cents: int
    last_24h_cents: int
    last_7d_cents: int
    refunded_cents: int


class AnalyticsOverviewOut(BaseModel):
    # Account funnel
    accounts_total: int
    accounts_dau: int          # distinct account_ids active (battled or attacked) in last 24h
    accounts_wau: int          # same, last 7 days
    accounts_banned: int
    accounts_verified: int
    accounts_with_2fa: int

    # Monetization
    payers_total: int          # accounts with ≥1 COMPLETED purchase
    payer_conversion_pct: float
    revenue: AnalyticsRevenueOut
    purchases: AnalyticsBucket

    # Engagement
    battles: AnalyticsBucket
    arena_matches: AnalyticsBucket
    raid_attempts: AnalyticsBucket
    summons: AnalyticsBucket
    avg_summons_per_account: float


@router.get("/analytics/overview", response_model=AnalyticsOverviewOut)
def analytics_overview(
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalyticsOverviewOut:
    """Product-level overview. Reads existing tables — no new schema."""
    # Imports here to avoid bloating the module-top (these are only used in this one place).
    from app.models import (
        ArenaMatch as _AM,
        GachaRecord as _GR,
        Purchase as _P,
        PurchaseState as _PS,
        RaidAttempt as _RA,
    )

    now = utcnow()
    d1 = now - timedelta(hours=24)
    d7 = now - timedelta(days=7)

    def _count(stmt) -> int:
        return db.scalar(stmt) or 0

    # --- accounts ---
    accounts_total = _count(select(func.count(Account.id)))
    accounts_banned = _count(select(func.count(Account.id)).where(Account.is_banned.is_(True)))
    accounts_verified = _count(select(func.count(Account.id)).where(Account.email_verified.is_(True)))
    accounts_with_2fa = _count(select(func.count(Account.id)).where(Account.totp_enabled.is_(True)))

    # DAU/WAU: distinct account_id from Battle OR ArenaMatch in the window.
    # Union of two distinct-selects into a CTE-like subquery is cleanest in raw SQL,
    # but here we compose it: distinct battle actors + distinct arena actors, dedup.
    def _active_ids(since) -> set[int]:
        battle_ids = set(db.scalars(
            select(Battle.account_id).where(Battle.created_at >= since).distinct()
        ))
        arena_ids = set(db.scalars(
            select(_AM.attacker_id).where(_AM.created_at >= since).distinct()
        ))
        return battle_ids | arena_ids

    dau = len(_active_ids(d1))
    wau = len(_active_ids(d7))

    # --- monetization ---
    payers_total = _count(
        select(func.count(func.distinct(_P.account_id)))
        .where(_P.state == _PS.COMPLETED)
    )
    payer_conversion_pct = round(
        100 * payers_total / accounts_total, 2
    ) if accounts_total else 0.0

    total_cents = _count(
        select(func.coalesce(func.sum(_P.price_cents_paid), 0))
        .where(_P.state == _PS.COMPLETED)
    )
    last_24h_cents = _count(
        select(func.coalesce(func.sum(_P.price_cents_paid), 0))
        .where(_P.state == _PS.COMPLETED, _P.completed_at >= d1)
    )
    last_7d_cents = _count(
        select(func.coalesce(func.sum(_P.price_cents_paid), 0))
        .where(_P.state == _PS.COMPLETED, _P.completed_at >= d7)
    )
    refunded_cents = _count(
        select(func.coalesce(func.sum(_P.price_cents_paid), 0))
        .where(_P.state == _PS.REFUNDED)
    )

    purchases_bucket = AnalyticsBucket(
        last_24h=_count(
            select(func.count(_P.id))
            .where(_P.state == _PS.COMPLETED, _P.completed_at >= d1)
        ),
        last_7d=_count(
            select(func.count(_P.id))
            .where(_P.state == _PS.COMPLETED, _P.completed_at >= d7)
        ),
        total=_count(select(func.count(_P.id)).where(_P.state == _PS.COMPLETED)),
    )

    # --- engagement ---
    battles_bucket = AnalyticsBucket(
        last_24h=_count(select(func.count(Battle.id)).where(Battle.created_at >= d1)),
        last_7d=_count(select(func.count(Battle.id)).where(Battle.created_at >= d7)),
        total=_count(select(func.count(Battle.id))),
    )
    arena_bucket = AnalyticsBucket(
        last_24h=_count(select(func.count(_AM.id)).where(_AM.created_at >= d1)),
        last_7d=_count(select(func.count(_AM.id)).where(_AM.created_at >= d7)),
        total=_count(select(func.count(_AM.id))),
    )
    raid_bucket = AnalyticsBucket(
        last_24h=_count(select(func.count(_RA.id)).where(_RA.created_at >= d1)),
        last_7d=_count(select(func.count(_RA.id)).where(_RA.created_at >= d7)),
        total=_count(select(func.count(_RA.id))),
    )
    summons_bucket = AnalyticsBucket(
        last_24h=_count(select(func.count(_GR.id)).where(_GR.pulled_at >= d1)),
        last_7d=_count(select(func.count(_GR.id)).where(_GR.pulled_at >= d7)),
        total=_count(select(func.count(_GR.id))),
    )

    avg_summons = round(summons_bucket.total / accounts_total, 2) if accounts_total else 0.0

    return AnalyticsOverviewOut(
        accounts_total=accounts_total,
        accounts_dau=dau,
        accounts_wau=wau,
        accounts_banned=accounts_banned,
        accounts_verified=accounts_verified,
        accounts_with_2fa=accounts_with_2fa,
        payers_total=payers_total,
        payer_conversion_pct=payer_conversion_pct,
        revenue=AnalyticsRevenueOut(
            total_cents=total_cents,
            last_24h_cents=last_24h_cents,
            last_7d_cents=last_7d_cents,
            refunded_cents=refunded_cents,
        ),
        purchases=purchases_bucket,
        battles=battles_bucket,
        arena_matches=arena_bucket,
        raid_attempts=raid_bucket,
        summons=summons_bucket,
        avg_summons_per_account=avg_summons,
    )
