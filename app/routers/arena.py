import json
import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.combat import power_rating, scale_stat, simulate
from app.daily import on_arena_attack
from app.db import get_db
from app.deps import get_current_account
from app.gear_logic import gear_bonus_for
from app.models import (
    Account,
    ArenaMatch,
    BattleOutcome,
    DefenseTeam,
    HeroInstance,
    utcnow,
)
from app.routers.battles import _unit_from_instance
from app.routers.heroes import instance_out
from app.schemas import (
    ArenaAttackIn,
    ArenaLeaderboardEntry,
    ArenaMatchOut,
    ArenaOpponentOut,
    DefenseSetIn,
    HeroInstanceOut,
)

router = APIRouter(prefix="/arena", tags=["arena"])


RATING_WIN = 25
RATING_LOSS = -15
MIN_RATING = 0
OPPONENT_SAMPLE_SIZE = 3


def _compute_team_power(heroes: list[HeroInstance]) -> int:
    total = 0
    for h in heroes:
        t = h.template
        hp = scale_stat(t.base_hp, h.level)
        atk = scale_stat(t.base_atk, h.level)
        df = scale_stat(t.base_def, h.level)
        spd = t.base_spd
        bonus = gear_bonus_for(h)
        total += power_rating(hp + bonus["hp"], atk + bonus["atk"], df + bonus["def"], spd + bonus["spd"])
    return total


def _load_heroes(db: Session, account: Account, ids: list[int]) -> list[HeroInstance]:
    heroes: list[HeroInstance] = []
    for hid in ids:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")
        heroes.append(h)
    return heroes


@router.put("/defense", response_model=dict)
def set_defense(
    body: DefenseSetIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    heroes = _load_heroes(db, account, body.team)
    power = _compute_team_power(heroes)
    dt = db.get(DefenseTeam, account.id)
    now = utcnow()
    if dt is None:
        dt = DefenseTeam(
            account_id=account.id,
            hero_ids_json=json.dumps(body.team),
            power=power,
            updated_at=now,
        )
        db.add(dt)
    else:
        dt.hero_ids_json = json.dumps(body.team)
        dt.power = power
        dt.updated_at = now
    db.commit()
    return {"team": body.team, "power": power}


@router.get("/defense", response_model=dict)
def get_defense(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    dt = db.get(DefenseTeam, account.id)
    if dt is None:
        return {"team": [], "power": 0}
    try:
        team = json.loads(dt.hero_ids_json)
    except json.JSONDecodeError:
        team = []
    return {"team": team, "power": dt.power}


@router.get("/opponents", response_model=list[ArenaOpponentOut])
def list_opponents(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ArenaOpponentOut]:
    # Pool: accounts with a defense team set, excluding the caller.
    pool_ids = list(
        db.scalars(
            select(DefenseTeam.account_id).where(DefenseTeam.account_id != account.id)
        )
    )
    if not pool_ids:
        return []
    rng = random.Random()
    rng.shuffle(pool_ids)
    chosen = pool_ids[:OPPONENT_SAMPLE_SIZE]

    out: list[ArenaOpponentOut] = []
    for acct_id in chosen:
        opp = db.get(Account, acct_id)
        dt = db.get(DefenseTeam, acct_id)
        if opp is None or dt is None:
            continue
        try:
            ids = json.loads(dt.hero_ids_json)
        except json.JSONDecodeError:
            continue
        hero_out: list[HeroInstanceOut] = []
        for hid in ids:
            h = db.get(HeroInstance, hid)
            if h is None or h.account_id != acct_id:
                continue
            hero_out.append(instance_out(h))
        if not hero_out:
            continue
        out.append(ArenaOpponentOut(
            account_id=opp.id,
            name=opp.email.split("@")[0],
            arena_rating=opp.arena_rating,
            team_power=dt.power,
            team=hero_out,
        ))
    return out


@router.post("/attack", response_model=ArenaMatchOut, status_code=status.HTTP_201_CREATED)
def attack(
    body: ArenaAttackIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> ArenaMatchOut:
    if body.defender_account_id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot attack self")
    defender = db.get(Account, body.defender_account_id)
    if defender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "defender not found")
    dt = db.get(DefenseTeam, defender.id)
    if dt is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "defender has no defense team set")

    attackers = _load_heroes(db, account, body.team)
    try:
        def_ids = json.loads(dt.hero_ids_json)
    except json.JSONDecodeError:
        def_ids = []
    defenders: list[HeroInstance] = []
    for hid in def_ids:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != defender.id:
            continue
        defenders.append(h)
    if not defenders:
        raise HTTPException(status.HTTP_409_CONFLICT, "defender team is empty or invalid")

    team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(attackers)]
    team_b = [_unit_from_instance(h, "B", i) for i, h in enumerate(defenders)]

    rng = random.Random()
    result = simulate(team_a, team_b, rng)

    if result.outcome == BattleOutcome.WIN:
        delta = RATING_WIN
        account.arena_wins += 1
        defender.arena_losses += 1
    elif result.outcome == BattleOutcome.LOSS:
        delta = RATING_LOSS
        account.arena_losses += 1
        defender.arena_wins += 1
    else:
        delta = 0

    account.arena_rating = max(MIN_RATING, account.arena_rating + delta)
    defender.arena_rating = max(MIN_RATING, defender.arena_rating - delta)

    on_arena_attack(db, account)

    match = ArenaMatch(
        attacker_id=account.id,
        defender_id=defender.id,
        outcome=result.outcome,
        rating_delta=delta,
        attacker_rating_after=account.arena_rating,
        defender_rating_after=defender.arena_rating,
        log_json=json.dumps(result.log),
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return ArenaMatchOut(
        id=match.id,
        attacker_id=match.attacker_id,
        defender_id=match.defender_id,
        outcome=result.outcome,
        rating_delta=delta,
        attacker_rating_after=account.arena_rating,
        defender_rating_after=defender.arena_rating,
        log=result.log,
        created_at=match.created_at,
    )


@router.get("/leaderboard", response_model=list[ArenaLeaderboardEntry])
def leaderboard(db: Annotated[Session, Depends(get_db)]) -> list[ArenaLeaderboardEntry]:
    rows = db.execute(
        select(Account.id, Account.email, Account.arena_rating, Account.arena_wins, Account.arena_losses)
        .order_by(desc(Account.arena_rating), Account.id)
        .limit(20)
    )
    return [
        ArenaLeaderboardEntry(
            account_id=r[0], email=r[1], arena_rating=r[2], arena_wins=r[3], arena_losses=r[4]
        )
        for r in rows
    ]
