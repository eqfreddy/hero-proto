"""AFK income loop — passive coin/XP accrual while offline.

The genre-defining hook (AFK Arena, Hero Wars, etc.). Players accrue
gold and per-hero XP at a rate scaled to account level. They tap a
button on the dashboard to bank the pending pool. Accrual caps at
AFK_MAX_HOURS so the loop creates 1-2 daily logins, not 'log in once
a week and skim'.

Tuning knobs sit at the top of this module; future seasonal events can
swap COINS_PER_HOUR_BASE temporarily for double-AFK weekends.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Account, HeroInstance, utcnow

AFK_MAX_HOURS = 12.0
# Coins per hour at account_level=1. Linear scaling: level 10 = 1500 c/h.
COINS_PER_HOUR_BASE = 150
COINS_PER_HOUR_PER_LEVEL = 150
# Hero XP per hour at account_level=1, distributed across the 3 highest-power
# heroes (mirroring the player's likely 'main team').
HERO_XP_PER_HOUR_BASE = 30
HERO_XP_PER_HOUR_PER_LEVEL = 20
HERO_XP_TOP_N = 3


def _seconds_since(account: Account, now: datetime) -> float:
    base = account.afk_last_collected_at
    if base is None:
        # First-ever claim: treat the player's account creation as the start so
        # they don't see a giant pool from "the dawn of time" if the column was
        # never initialized.
        base = account.created_at or now
    delta = (now - base).total_seconds()
    return max(0.0, delta)


def _max_hours_for(account: Account) -> float:
    """Base 12h cap, extended by VIP tier perks. VIP 1 gets 13h, max VIP 36h."""
    from app.vip import perks_for_account
    return float(perks_for_account(account).get("afk_cap_hours", AFK_MAX_HOURS))


def _capped_seconds(account: Account, now: datetime) -> float:
    return min(_seconds_since(account, now), _max_hours_for(account) * 3600)


def _level(account: Account) -> int:
    return max(1, int(account.account_level or 1))


def coins_per_hour(account: Account) -> int:
    return COINS_PER_HOUR_BASE + COINS_PER_HOUR_PER_LEVEL * (_level(account) - 1)


def hero_xp_per_hour(account: Account) -> int:
    return HERO_XP_PER_HOUR_BASE + HERO_XP_PER_HOUR_PER_LEVEL * (_level(account) - 1)


def pending(account: Account, now: datetime | None = None) -> dict:
    """Compute pending accrual without granting it. Pure function — safe to
    call from /me on every request."""
    now = now or utcnow()
    max_hours = _max_hours_for(account)
    secs = _capped_seconds(account, now)
    raw_secs = _seconds_since(account, now)
    cap_secs = max_hours * 3600
    coins = int(coins_per_hour(account) * (secs / 3600))
    hero_xp_total = int(hero_xp_per_hour(account) * (secs / 3600))
    return {
        "pending_coins": coins,
        "pending_hero_xp": hero_xp_total,
        "hours_accrued": round(secs / 3600, 2),
        "hours_max": max_hours,
        "is_at_cap": raw_secs >= cap_secs,
        "coins_per_hour": coins_per_hour(account),
        "hero_xp_per_hour": hero_xp_per_hour(account),
    }


def _top_heroes(db: Session, account: Account, n: int = HERO_XP_TOP_N) -> list[HeroInstance]:
    rows = db.query(HeroInstance).filter_by(account_id=account.id).all()
    if not rows:
        return []
    # 'Power' is materialized via a model property; sort in Python to avoid
    # complicating the SQL.
    rows.sort(key=lambda h: getattr(h, "power", 0) or 0, reverse=True)
    return rows[:n]


def claim(db: Session, account: Account, now: datetime | None = None) -> dict:
    """Bank pending accrual. Splits hero XP equally across the top N heroes.
    Resets afk_last_collected_at to `now`. Idempotent in spirit — second
    claim with no time passing returns granted={zeros}."""
    now = now or utcnow()
    snapshot = pending(account, now)
    coins = snapshot["pending_coins"]
    hero_xp_total = snapshot["pending_hero_xp"]
    granted = {"coins": 0, "hero_xp": 0, "heroes_xp_grants": []}

    if coins > 0:
        account.coins = int(account.coins or 0) + coins
        granted["coins"] = coins

    heroes = _top_heroes(db, account)
    if heroes and hero_xp_total > 0:
        per_hero = hero_xp_total // len(heroes)
        if per_hero > 0:
            from app.economy import apply_xp
            actual_total = 0
            for h in heroes:
                apply_xp(h, per_hero)
                granted["heroes_xp_grants"].append({"hero_id": h.id, "xp": per_hero})
                actual_total += per_hero
            granted["hero_xp"] = actual_total

    account.afk_last_collected_at = now
    return granted
