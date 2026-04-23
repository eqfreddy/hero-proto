"""LiveOps event helpers — query active events + apply their multipliers."""

from __future__ import annotations

import json
from datetime import datetime

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
