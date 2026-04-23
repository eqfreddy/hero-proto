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
    Guild,
    GuildMember,
    HeroInstance,
    HeroTemplate,
    Raid,
    RaidAttempt,
    RaidState,
    Role,
    utcnow,
)
from app.schemas import RaidAttackIn, RaidAttackOut, RaidContributor, RaidOut, RaidStartIn

router = APIRouter(prefix="/raids", tags=["raids"])

# Boss HP = template-scaled HP × this multiplier. Keeps raids a shared, multi-session fight.
BOSS_HP_MULTIPLIER = 30
RAID_ENERGY_COST = 10
# Guild-wide reward pool when boss falls; split evenly among contributors.
RAID_DEFEAT_COINS = 2000
RAID_DEFEAT_GEMS = 50
RAID_DEFEAT_SHARDS = 5


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

    max_hp = scale_stat(boss.base_hp, body.boss_level) * BOSS_HP_MULTIPLIER
    now = utcnow()
    raid = Raid(
        guild_id=membership.guild_id,
        boss_template_id=boss.id,
        boss_level=body.boss_level,
        max_hp=max_hp,
        remaining_hp=max_hp,
        state=RaidState.ACTIVE,
        started_at=now,
        ends_at=now + timedelta(hours=body.duration_hours),
        started_by=account.id,
    )
    db.add(raid)
    db.commit()
    db.refresh(raid)
    return _raid_out(db, raid)


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

    return RaidAttackOut(
        damage_dealt=damage,
        boss_remaining_hp=raid.remaining_hp,
        boss_defeated=defeated,
        rewards=rewards_payload,
    )


def _distribute_rewards(db: Session, raid: Raid) -> dict:
    """Pay out rewards proportionally to contribution; minimum payout for any participant."""
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
        coins = max(100, int(round(RAID_DEFEAT_COINS * share)))
        gems = max(5, int(round(RAID_DEFEAT_GEMS * share)))
        shards = max(1, int(round(RAID_DEFEAT_SHARDS * share)))
        a.coins += coins
        a.gems += gems
        a.shards += shards
        paid[acct_id] = {"coins": coins, "gems": gems, "shards": shards}
    return {"total_contributions": contributions, "payouts": paid}
