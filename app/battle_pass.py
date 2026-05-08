"""Battle Pass core logic — seasons, XP, tier math, claim, premium grant.

Design:
- One ACTIVE BattlePassSeason at a time. `seed_active_season` is idempotent
  and called from app.seed.seed().
- AccountBattlePass is created lazily on first XP grant or GET.
- Tier from xp = min(max_tier, xp_total // xp_per_tier).
- Tracks: 50 tiers, free + premium parallel reward tables.
- record_event() is fire-and-forget (mirrors quest_service pattern).
- purchase_premium grants the premium track for the active season; existing
  Purchase audit row is the refund source of truth.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountBattlePass, BattlePassSeason, utcnow

log = logging.getLogger(__name__)

# XP awarded per gameplay event. Tunable; total ~10k XP in a 30-day season at
# moderate engagement (~1 hour/day) lands a free player around tier 30-40.
XP_PER_EVENT: dict[str, int] = {
    "BATTLE_COMPLETE": 5,
    "BATTLE_WIN": 10,
    "STAGE_CLEARED": 25,
    "HARD_STAGE_CLEARED": 40,
    "LEGENDARY_STAGE_CLEARED": 80,
    "STORY_CHAPTER_CLEARED": 150,
    "ARENA_WIN": 30,
    "RAID_CONTRIBUTED": 50,
    "DAILY_QUEST_COMPLETE": 75,
    "GUILD_RAID_KILL": 200,
    "SUMMON_X10": 40,
}


def _grant_caps_per_day(event: str) -> int | None:
    """Soft cap per event per day to prevent farming. None = uncapped."""
    return {
        "BATTLE_WIN": 50,        # max 500 XP/day from grinding battles
        "STAGE_CLEARED": 20,
        "HARD_STAGE_CLEARED": 15,
        "LEGENDARY_STAGE_CLEARED": 10,
        "ARENA_WIN": 15,
        "DAILY_QUEST_COMPLETE": 8,
    }.get(event)


SEASON_DURATION_DAYS = 30


def _default_tracks(max_tier: int = 50) -> dict[str, list[dict]]:
    """Generate the default Season-1 reward tables.

    Free track: light gem/coin trickle, +1 epic shard pack at tier 25 +
    1 extra summon ticket-equivalent at tier 50.
    Premium track: substantially fatter — gems, shards, named-armor token at
    tier 25, mythic-tier resource at tier 50.
    """
    free: list[dict] = []
    premium: list[dict] = []
    for tier in range(1, max_tier + 1):
        # Free: 50 coins every tier, 25 gems every 5th tier, milestones at 10/25/50.
        free.append({"tier": tier, "kind": "coins", "amount": 200})
        if tier % 5 == 0:
            free.append({"tier": tier, "kind": "gems", "amount": 25})
        if tier == 10:
            free.append({"tier": tier, "kind": "shards", "amount": 50})
        if tier == 25:
            free.append({"tier": tier, "kind": "shards", "amount": 100})
        if tier == 50:
            free.append({"tier": tier, "kind": "gems", "amount": 200})

        # Premium: 50 gems every tier, ramping milestones.
        premium.append({"tier": tier, "kind": "gems", "amount": 50})
        if tier % 3 == 0:
            premium.append({"tier": tier, "kind": "shards", "amount": 50})
        if tier == 10:
            premium.append({"tier": tier, "kind": "coins", "amount": 5000})
        if tier == 25:
            premium.append({"tier": tier, "kind": "shards", "amount": 300})
            premium.append({"tier": tier, "kind": "gems", "amount": 300})
        if tier == 40:
            premium.append({"tier": tier, "kind": "shards", "amount": 500})
        if tier == 50:
            premium.append({"tier": tier, "kind": "gems", "amount": 1000})
            premium.append({"tier": tier, "kind": "shards", "amount": 500})
    return {"free": free, "premium": premium}


def seed_active_season(db: Session, *, code: str = "season_1_boot_sector",
                       name: str = "Season 1: Boot Sector",
                       description: str = "The first month. Earn XP from every battle, stage clear, "
                                          "arena win, and raid contribution.",
                       max_tier: int = 50, xp_per_tier: int = 200,
                       premium_price_cents: int = 999) -> BattlePassSeason:
    """Idempotent: create the season if missing, otherwise return the existing row."""
    existing = db.scalar(select(BattlePassSeason).where(BattlePassSeason.code == code))
    if existing is not None:
        return existing
    now = utcnow()
    s = BattlePassSeason(
        code=code, name=name, description=description,
        starts_at=now, ends_at=now + timedelta(days=SEASON_DURATION_DAYS),
        max_tier=max_tier, xp_per_tier=xp_per_tier,
        premium_price_cents=premium_price_cents,
        tracks_json=json.dumps(_default_tracks(max_tier)),
        is_active=True,
    )
    db.add(s)
    db.flush()
    return s


def active_season(db: Session) -> BattlePassSeason | None:
    now = utcnow()
    return db.scalar(
        select(BattlePassSeason)
        .where(BattlePassSeason.is_active.is_(True),
               BattlePassSeason.starts_at <= now,
               BattlePassSeason.ends_at >= now)
        .order_by(BattlePassSeason.starts_at.desc())
    )


def get_or_create_pass(db: Session, account: Account, season: BattlePassSeason) -> AccountBattlePass:
    bp = db.scalar(
        select(AccountBattlePass).where(
            AccountBattlePass.account_id == account.id,
            AccountBattlePass.season_id == season.id,
        )
    )
    if bp is None:
        bp = AccountBattlePass(account_id=account.id, season_id=season.id)
        db.add(bp)
        db.flush()
    return bp


def tier_from_xp(xp: int, season: BattlePassSeason) -> int:
    return min(season.max_tier, max(0, xp // max(1, season.xp_per_tier)))


def record_event(db: Session, account: Account, event: str) -> None:
    """Award BP XP for an event. Fire-and-forget — never raises."""
    try:
        amount = XP_PER_EVENT.get(event)
        if amount is None or amount <= 0:
            return
        season = active_season(db)
        if season is None:
            return
        bp = get_or_create_pass(db, account, season)
        # NOTE: per-day caps are intentionally not enforced here yet — see
        # _grant_caps_per_day. Wiring them in needs a per-(season,event)
        # daily counter table; defer until we observe farming in metrics.
        bp.xp_total = int(bp.xp_total) + amount
    except Exception:
        log.exception("battle_pass record_event failed (event=%s account=%s)", event, account.id)


def _rewards_at_tier(track: list[dict], tier: int) -> list[dict]:
    return [r for r in track if int(r.get("tier", -1)) == tier]


def claim_tier(db: Session, account: Account, tier: int, *, track: str) -> dict:
    """Claim rewards at `tier` on `track` (free|premium). Idempotent — re-claim
    of the same tier returns granted={}. Raises ValueError on bad inputs."""
    if track not in ("free", "premium"):
        raise ValueError(f"track must be 'free' or 'premium', got {track!r}")
    season = active_season(db)
    if season is None:
        raise ValueError("no active battle pass season")
    if tier < 1 or tier > season.max_tier:
        raise ValueError(f"tier out of range 1..{season.max_tier}")
    bp = get_or_create_pass(db, account, season)
    current_tier = tier_from_xp(bp.xp_total, season)
    if tier > current_tier:
        raise ValueError(f"tier {tier} not unlocked (current={current_tier})")
    if track == "premium" and bp.premium_purchased_at is None:
        raise ValueError("premium track not purchased")
    claimed_field = "claimed_premium_json" if track == "premium" else "claimed_free_json"
    claimed: list[int] = json.loads(getattr(bp, claimed_field) or "[]")
    if tier in claimed:
        return {"granted": {}, "tier": tier, "track": track, "already_claimed": True}
    tracks = json.loads(season.tracks_json or '{"free":[],"premium":[]}')
    rewards = _rewards_at_tier(tracks.get(track, []), tier)
    granted: dict[str, int] = {}
    for r in rewards:
        kind = r.get("kind")
        amount = int(r.get("amount", 0))
        if kind == "gems":
            account.gems = int(account.gems) + amount
        elif kind == "shards":
            account.shards = int(account.shards) + amount
        elif kind == "coins":
            account.coins = int(account.coins) + amount
        else:
            log.warning("battle_pass: unknown reward kind %r in season %s tier %d",
                        kind, season.code, tier)
            continue
        granted[kind] = granted.get(kind, 0) + amount
    claimed.append(tier)
    setattr(bp, claimed_field, json.dumps(claimed))
    return {"granted": granted, "tier": tier, "track": track, "already_claimed": False}


def grant_premium(db: Session, account: Account, season: BattlePassSeason | None = None) -> AccountBattlePass:
    """Mark the premium track as purchased for the active (or given) season.
    Called from the shop purchase fulfillment path. Idempotent."""
    s = season or active_season(db)
    if s is None:
        raise ValueError("no active battle pass season")
    bp = get_or_create_pass(db, account, s)
    if bp.premium_purchased_at is None:
        bp.premium_purchased_at = utcnow()
    return bp


def state_for_account(db: Session, account: Account) -> dict[str, Any]:
    """Snapshot for GET /battle-pass — season meta + account progress + tracks."""
    season = active_season(db)
    if season is None:
        return {"active": False, "season": None, "progress": None}
    bp = get_or_create_pass(db, account, season)
    tracks = json.loads(season.tracks_json or '{"free":[],"premium":[]}')
    return {
        "active": True,
        "season": {
            "id": season.id,
            "code": season.code,
            "name": season.name,
            "description": season.description,
            "starts_at": season.starts_at.isoformat() if season.starts_at else None,
            "ends_at": season.ends_at.isoformat() if season.ends_at else None,
            "max_tier": season.max_tier,
            "xp_per_tier": season.xp_per_tier,
            "premium_price_cents": season.premium_price_cents,
            "tracks": tracks,
        },
        "progress": {
            "xp_total": bp.xp_total,
            "current_tier": tier_from_xp(bp.xp_total, season),
            "premium_purchased": bp.premium_purchased_at is not None,
            "claimed_free": json.loads(bp.claimed_free_json or "[]"),
            "claimed_premium": json.loads(bp.claimed_premium_json or "[]"),
        },
    }
