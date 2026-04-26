"""LiveOps event helpers — query active events + apply their multipliers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LiveOpsEvent, LiveOpsKind, utcnow


def active_events(db: Session, now: datetime | None = None) -> list[LiveOpsEvent]:
    now = now or utcnow()
    return list(
        db.scalars(
            select(LiveOpsEvent).where(
                LiveOpsEvent.starts_at <= now, LiveOpsEvent.ends_at > now
            )
        )
    )


def reward_multiplier(db: Session, now: datetime | None = None) -> float:
    """Aggregate DOUBLE_REWARDS multipliers. Stacks multiplicatively if overlapping."""
    total = 1.0
    for e in active_events(db, now):
        if (LiveOpsKind(e.kind) if not isinstance(e.kind, LiveOpsKind) else e.kind) != LiveOpsKind.DOUBLE_REWARDS:
            continue
        try:
            payload = json.loads(e.payload_json or "{}")
        except json.JSONDecodeError:
            continue
        m = float(payload.get("multiplier", 2.0))
        if m > 0:
            total *= m
    return total


def gear_drop_bonus(db: Session, now: datetime | None = None) -> float:
    """Additive flat bump to gear drop chance."""
    bonus = 0.0
    for e in active_events(db, now):
        if (LiveOpsKind(e.kind) if not isinstance(e.kind, LiveOpsKind) else e.kind) != LiveOpsKind.BONUS_GEAR_DROPS:
            continue
        try:
            payload = json.loads(e.payload_json or "{}")
        except json.JSONDecodeError:
            continue
        bonus += float(payload.get("chance_add", 0.2))
    return min(0.9, max(0.0, bonus))  # cap so battles don't always drop


def active_event_banner(db: Session, now: datetime | None = None) -> LiveOpsEvent | None:
    """Returns the currently-active EVENT_BANNER event, or None.

    Phase 2.2 — gates Myth-tier event-hero summons to the active window only.
    If multiple EVENT_BANNER events overlap (rare but legal — anniversary
    event running through a holiday), returns the one that started most
    recently so the most current banner wins.
    """
    candidates = [
        e for e in active_events(db, now)
        if (LiveOpsKind(e.kind) if not isinstance(e.kind, LiveOpsKind) else e.kind)
        == LiveOpsKind.EVENT_BANNER
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda e: e.starts_at, reverse=True)
    return candidates[0]


def event_banner_payload(event: LiveOpsEvent) -> dict:
    """Parsed payload for an EVENT_BANNER event. Required keys:
    `hero_template_code` (str). Optional: `shard_cost` (int, default 5),
    `per_account_cap` (int, default 3). Caller is responsible for
    handling missing required keys."""
    try:
        data = json.loads(event.payload_json or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "hero_template_code": str(data.get("hero_template_code", "")),
        "shard_cost": int(data.get("shard_cost", 5) or 5),
        "per_account_cap": int(data.get("per_account_cap", 3) or 3),
    }


def liveops_summary(db: Session) -> list[dict]:
    out = []
    for e in active_events(db):
        out.append({
            "id": e.id,
            "kind": str(e.kind),
            "name": e.name,
            "starts_at": e.starts_at.isoformat(),
            "ends_at": e.ends_at.isoformat(),
        })
    return out


def scheduled_events(db: Session, horizon_days: int = 7, now: datetime | None = None) -> list[LiveOpsEvent]:
    """Events that haven't started yet but will within the horizon. Sorted by start time."""
    now = now or utcnow()
    cutoff = now + timedelta(days=horizon_days)
    return list(
        db.scalars(
            select(LiveOpsEvent)
            .where(LiveOpsEvent.starts_at > now, LiveOpsEvent.starts_at <= cutoff)
            .order_by(LiveOpsEvent.starts_at)
        )
    )


def scheduled_summary(db: Session, horizon_days: int = 7) -> list[dict]:
    return [
        {
            "id": e.id,
            "kind": str(e.kind),
            "name": e.name,
            "starts_at": e.starts_at.isoformat(),
            "ends_at": e.ends_at.isoformat(),
        }
        for e in scheduled_events(db, horizon_days=horizon_days)
    ]
