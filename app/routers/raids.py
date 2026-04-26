"""Guild raid mechanics: shared-HP boss over a time window."""

from __future__ import annotations

import json
import random
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.combat import CombatUnit, build_unit, scale_stat, simulate
from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.economy import consume_energy
from app.gear_logic import gear_bonus_for
from app.models import (
    Account,
    BattleOutcome,
    Faction,
    Guild,
    GuildMember,
    HeroInstance,
    HeroTemplate,
    Raid,
    RaidAttempt,
    RaidState,
    RaidTier,
    Role,
    utcnow,
)
from app.schemas import RaidAttackIn, RaidAttackOut, RaidContributor, RaidOut, RaidStartIn

router = APIRouter(prefix="/raids", tags=["raids"])

# Boss HP = template-scaled HP × this multiplier. Keeps raids a shared, multi-session fight.
# Per-tier multipliers apply on top.
BOSS_HP_MULTIPLIER_BASE = 30
RAID_ENERGY_COST = 10
# Per-account cooldown between attacks on the SAME raid. Stops a guild member
# from hammering a fresh raid with a bot loop, and also paces the pool of
# contributors so it's not one person's score. Separate from /battles' global
# per-account rate limit — this is scoped to one raid.
RAID_ATTEMPT_COOLDOWN_SECONDS = 600  # 10 minutes
# Guild-wide base reward pool when boss falls; per-tier multipliers apply.
RAID_DEFEAT_COINS_BASE = 2000
RAID_DEFEAT_GEMS_BASE = 50
RAID_DEFEAT_SHARDS_BASE = 5

# Tier scaling: T2 is 2x T1 HP + rewards, T3 is 4x. Level bump for higher tiers too.
_TIER_HP_MULT = {RaidTier.T1: 1.0, RaidTier.T2: 2.0, RaidTier.T3: 4.0}
_TIER_REWARD_MULT = {RaidTier.T1: 1.0, RaidTier.T2: 2.0, RaidTier.T3: 4.0}
_TIER_LEVEL_BUMP = {RaidTier.T1: 0, RaidTier.T2: 10, RaidTier.T3: 25}


def _tier_enum(raid: Raid) -> RaidTier:
    return RaidTier(raid.tier) if not isinstance(raid.tier, RaidTier) else raid.tier


def boss_hp_for_tier(base_hp: int, level: int, tier: RaidTier) -> int:
    mult = BOSS_HP_MULTIPLIER_BASE * _TIER_HP_MULT[tier]
    return int(scale_stat(base_hp, level + _TIER_LEVEL_BUMP[tier]) * mult)


def _require_guild(db: Session, account: Account) -> GuildMember:
    m = db.get(GuildMember, account.id)
    if m is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not in a guild")
    return m


def _raid_out(db: Session, raid: Raid) -> RaidOut:
    boss = db.get(HeroTemplate, raid.boss_template_id)
    rows = db.execute(
        select(RaidAttempt.account_id, func.sum(RaidAttempt.damage_dealt), Account.email)
        .join(Account, Account.id == RaidAttempt.account_id)
        .where(RaidAttempt.raid_id == raid.id)
        .group_by(RaidAttempt.account_id, Account.email)
        .order_by(func.sum(RaidAttempt.damage_dealt).desc())
    )
    contributors = [
        RaidContributor(
            account_id=r[0],
            name=r[2].split("@")[0] if r[2] else f"#{r[0]}",
            damage_dealt=int(r[1] or 0),
        )
        for r in rows
    ]
    return RaidOut(
        id=raid.id,
        guild_id=raid.guild_id,
        boss_name=boss.name if boss else "???",
        boss_level=raid.boss_level,
        max_hp=raid.max_hp,
        remaining_hp=raid.remaining_hp,
        state=RaidState(raid.state) if not isinstance(raid.state, RaidState) else raid.state,
        tier=str(_tier_enum(raid)),
        starts_at=raid.started_at,
        ends_at=raid.ends_at,
        contributors=contributors,
    )


@router.post("/start", response_model=RaidOut, status_code=status.HTTP_201_CREATED)
def start_raid(
    body: RaidStartIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> RaidOut:
    membership = _require_guild(db, account)
    if str(membership.role) == "MEMBER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "officers or leader only")

    # One active raid per guild.
    existing = db.scalar(
        select(Raid).where(Raid.guild_id == membership.guild_id, Raid.state == RaidState.ACTIVE)
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "guild already has an active raid")

    boss = db.scalar(select(HeroTemplate).where(HeroTemplate.code == body.boss_template_code))
    if boss is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "boss template not found")

    tier = RaidTier(body.tier)
    max_hp = boss_hp_for_tier(boss.base_hp, body.boss_level, tier)
    now = utcnow()
    raid = Raid(
        guild_id=membership.guild_id,
        boss_template_id=boss.id,
        boss_level=body.boss_level,
        max_hp=max_hp,
        remaining_hp=max_hp,
        state=RaidState.ACTIVE,
        tier=tier,
        started_at=now,
        ends_at=now + timedelta(hours=body.duration_hours),
        started_by=account.id,
    )
    db.add(raid)
    db.commit()
    db.refresh(raid)
    return _raid_out(db, raid)


@router.get("/leaderboard", response_model=list[dict])
def raid_leaderboard(
    db: Annotated[Session, Depends(get_db)],
    days: int = 7,
    limit: int = 25,
) -> list[dict]:
    """Top-contributing guilds by total raid damage over the last `days`.

    Public — no auth needed. Use for a hall-of-fame widget. Bounded limit
    so one slow query can't dominate.
    """
    days = max(1, min(30, days))
    limit = max(1, min(100, limit))
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(
            Guild.id,
            Guild.name,
            Guild.tag,
            func.sum(RaidAttempt.damage_dealt),
            func.count(func.distinct(RaidAttempt.account_id)),
        )
        .join(Raid, Raid.id == RaidAttempt.raid_id)
        .join(Guild, Guild.id == Raid.guild_id)
        .where(RaidAttempt.created_at >= since)
        .group_by(Guild.id, Guild.name, Guild.tag)
        .order_by(func.sum(RaidAttempt.damage_dealt).desc())
        .limit(limit)
    )
    return [
        {
            "guild_id": int(r[0]),
            "name": r[1],
            "tag": r[2],
            "total_damage": int(r[3] or 0),
            "contributors": int(r[4] or 0),
        }
        for r in rows
    ]


@router.get("/mine", response_model=RaidOut | None)
def my_guild_raid(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> RaidOut | None:
    membership = _require_guild(db, account)
    raid = db.scalar(
        select(Raid)
        .where(Raid.guild_id == membership.guild_id, Raid.state == RaidState.ACTIVE)
        .order_by(Raid.started_at.desc())
    )
    if raid is None:
        return None
    return _raid_out(db, raid)


@router.get("/{raid_id}", response_model=RaidOut)
def get_raid(
    raid_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> RaidOut:
    membership = _require_guild(db, account)
    raid = db.get(Raid, raid_id)
    if raid is None or raid.guild_id != membership.guild_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "raid not found in your guild")
    return _raid_out(db, raid)


@router.post("/{raid_id}/attack", response_model=RaidAttackOut, status_code=status.HTTP_201_CREATED)
def attack_raid(
    raid_id: int,
    body: RaidAttackIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> RaidAttackOut:
    membership = _require_guild(db, account)
    raid = db.get(Raid, raid_id)
    if raid is None or raid.guild_id != membership.guild_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "raid not found in your guild")
    if raid.state != RaidState.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"raid is {raid.state}")
    now = utcnow()
    if raid.ends_at <= now:
        raid.state = RaidState.EXPIRED
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "raid has expired")

    # Per-account cooldown against THIS raid. Bypassed in tests (where
    # lifecycle tests hammer hundreds of attacks) and when rate-limiting
    # is globally disabled.
    if not (settings.rate_limit_disabled or settings.environment == "test"):
        last = db.scalar(
            select(RaidAttempt)
            .where(RaidAttempt.raid_id == raid.id, RaidAttempt.account_id == account.id)
            .order_by(RaidAttempt.created_at.desc())
            .limit(1)
        )
        if last is not None:
            elapsed = (now - last.created_at).total_seconds()
            if elapsed < RAID_ATTEMPT_COOLDOWN_SECONDS:
                retry = int(RAID_ATTEMPT_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"raid attempt cooldown — try again in {retry}s",
                    headers={"Retry-After": str(retry)},
                )

    heroes: list[HeroInstance] = []
    for hid in body.team:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")
        heroes.append(h)

    if not consume_energy(account, RAID_ENERGY_COST):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"not enough energy (need {RAID_ENERGY_COST})"
        )

    # Use the standard combat resolver but with a solo boss unit at 100% HP.
    # The boss's actual HP pool is the raid's remaining_hp; the sim just computes
    # how much damage your team *would* do vs a representative copy, then we apply
    # it to the shared pool.
    boss_template = db.get(HeroTemplate, raid.boss_template_id)
    try:
        special = json.loads(boss_template.special_json or "null")
    except json.JSONDecodeError:
        special = None

    def _faction(t: HeroTemplate) -> Faction | None:
        f = t.faction
        if f is None:
            return None
        return f if isinstance(f, Faction) else Faction(f)

    team_a = [
        build_unit(
            uid=f"A{i}",
            side="A",
            name=h.template.name,
            role=Role(h.template.role) if not isinstance(h.template.role, Role) else h.template.role,
            level=h.level,
            base_hp=h.template.base_hp,
            base_atk=h.template.base_atk,
            base_def=h.template.base_def,
            base_spd=h.template.base_spd,
            basic_mult=h.template.basic_mult,
            special=json.loads(h.template.special_json or "null"),
            special_cooldown=h.template.special_cooldown,
            gear_bonus=gear_bonus_for(h),
            special_level=h.special_level,
            stars=h.stars,
            faction=_faction(h.template),
        )
        for i, h in enumerate(heroes)
    ]
    # Boss copy uses a hefty hp pool so the sim runs long enough to generate
    # meaningful damage; we cap by remaining raid hp afterward.
    boss_unit = build_unit(
        uid="B0",
        side="B",
        name=boss_template.name,
        role=Role(boss_template.role) if not isinstance(boss_template.role, Role) else boss_template.role,
        level=raid.boss_level,
        base_hp=boss_template.base_hp * 10,
        base_atk=boss_template.base_atk,
        base_def=boss_template.base_def,
        base_spd=boss_template.base_spd,
        basic_mult=boss_template.basic_mult,
        special=special,
        special_cooldown=boss_template.special_cooldown,
        faction=_faction(boss_template),
    )
    boss_start_hp = boss_unit.hp
    rng = random.Random()
    # Cap to ~12 game ticks so a single attack isn't unbounded.
    # We use the existing simulate but the boss is tanky enough not to die.
    result = simulate(team_a, [boss_unit], rng)
    damage = max(1, boss_start_hp - boss_unit.hp)
    # Clamp so we don't underflow the shared HP pool.
    damage = min(damage, raid.remaining_hp)
    raid.remaining_hp -= damage

    db.add(RaidAttempt(raid_id=raid.id, account_id=account.id, damage_dealt=damage))

    # Daily-quest hook: RAID_DAMAGE advances by the raw damage dealt this attack.
    from app.daily import on_raid_damage
    on_raid_damage(db, account, damage)
    # Event hook: count one raid attack regardless of damage value.
    from app.event_state import QUEST_KINDS_RAID, on_activity as _event_on_activity
    _event_on_activity(db, account, "raid_attack", quest_kinds=QUEST_KINDS_RAID)
    # Crafting material drops — every raid attack rolls the raid pool.
    from app.crafting import grant_material as _grant_mat, roll_raid_drops
    raid_mat_drops = roll_raid_drops(rng)
    for code, qty in raid_mat_drops:
        _grant_mat(db, account, code, qty)
    # Achievements: raid_1 + raid_25.
    from app.achievements import check_achievements as _ca
    _ca(db, account)
    # Account XP for raid attacks.
    from app.account_level import XP_PER_RAID_ATTACK, grant_xp as _gxp
    _gxp(db, account, XP_PER_RAID_ATTACK)

    rewards_payload: dict | None = None
    defeated = False
    if raid.remaining_hp <= 0:
        raid.remaining_hp = 0
        raid.state = RaidState.DEFEATED
        defeated = True
        rewards_payload = _distribute_rewards(db, raid)
    db.commit()

    # Suppress unused-var lint.
    _ = result.outcome

    from app.analytics import track as _track
    _track("raid_attack", account.id, {
        "raid_id": raid.id,
        "tier": str(raid.tier),
        "damage_dealt": damage,
        "boss_defeated": defeated,
        "boss_remaining_pct": (
            round(100 * raid.remaining_hp / raid.max_hp, 1) if raid.max_hp > 0 else 0
        ),
    })

    return RaidAttackOut(
        damage_dealt=damage,
        boss_remaining_hp=raid.remaining_hp,
        boss_defeated=defeated,
        rewards=rewards_payload,
    )


def _distribute_rewards(db: Session, raid: Raid) -> dict:
    """Pay out rewards proportionally to contribution; minimum payout for any participant.

    Tier multiplier scales the whole pool — T2 pays double, T3 pays quadruple the
    T1 base values.
    """
    tier = _tier_enum(raid)
    mult = _TIER_REWARD_MULT[tier]
    coin_pool = int(RAID_DEFEAT_COINS_BASE * mult)
    gem_pool = int(RAID_DEFEAT_GEMS_BASE * mult)
    shard_pool = int(RAID_DEFEAT_SHARDS_BASE * mult)

    rows = db.execute(
        select(RaidAttempt.account_id, func.sum(RaidAttempt.damage_dealt))
        .where(RaidAttempt.raid_id == raid.id)
        .group_by(RaidAttempt.account_id)
    )
    contributions = {int(r[0]): int(r[1] or 0) for r in rows}
    total = sum(contributions.values()) or 1
    paid: dict[int, dict[str, int]] = {}
    for acct_id, dmg in contributions.items():
        share = dmg / total
        a = db.get(Account, acct_id)
        if a is None:
            continue
        coins = max(100, int(round(coin_pool * share)))
        gems = max(5, int(round(gem_pool * share)))
        shards = max(1, int(round(shard_pool * share)))
        a.coins += coins
        a.gems += gems
        a.shards += shards
        paid[acct_id] = {"coins": coins, "gems": gems, "shards": shards}
    return {"total_contributions": contributions, "payouts": paid, "tier": str(tier)}
