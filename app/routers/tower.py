"""Tower of Trials — endless solo climb.

Mechanics
- Each player has a current floor (1+) and an all-time best floor.
- 3 daily attempts per UTC day; capped to keep the climb a marathon
  not a sprint. Refresh on UTC midnight.
- Each attempt is one battle vs a procedurally-scaled enemy team.
- Win → advance one floor + grant scaling rewards (coins, gems every
  5 floors, shards every 10, +template-shards on the player's heroes
  at floor 25/50/75/...).
- Loss → no advance, attempt consumed.
- Monthly season key: when it rolls, tower_floor resets to 1 but
  tower_best_floor (PB) persists. Cheap leaderboard pivot point.

GET  /tower               — status (floor, best, attempts, season)
POST /tower/attempt       — body {team: [hero_instance_id, ...]}
GET  /tower/leaderboard   — top players by tower_best_floor
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.combat import simulate
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, HeroInstance, HeroTemplate, Rarity, utcnow
from app.routers.battles import _unit_from_instance, _unit_from_template

router = APIRouter(prefix="/tower", tags=["tower"])


DAILY_ATTEMPTS = 3
SEASON_RESET_KEEPS_PB = True


def _today_utc_midnight() -> datetime:
    n = utcnow()
    return datetime(n.year, n.month, n.day)


def _current_season_key() -> str:
    n = utcnow()
    return f"{n.year:04d}-{n.month:02d}"


def _reset_daily_if_stale(account: Account) -> None:
    today = _today_utc_midnight()
    if account.tower_attempts_today_date != today:
        account.tower_attempts_today = 0
        account.tower_attempts_today_date = today


def _reset_season_if_stale(account: Account) -> None:
    sk = _current_season_key()
    if account.tower_season_key != sk:
        # Carry over PB only if the player has actually played this season
        # (season_key was set to a real value before). First-ever /tower hit
        # on a new account just stamps the season key with no PB shuffle.
        if account.tower_season_key:
            account.tower_best_floor = max(
                int(account.tower_best_floor or 0),
                int(account.tower_floor or 1),
            )
            account.tower_floor = 1
        account.tower_season_key = sk


def _enemy_count_for_floor(floor: int) -> int:
    # 1 enemy on floor 1, gradually scale to 3 by floor 5.
    if floor < 3:
        return 1
    if floor < 5:
        return 2
    return 3


def _enemy_level_for_floor(floor: int) -> int:
    return max(1, floor)


def _build_enemy_team(db: Session, floor: int, rng: random.Random):
    # Pull templates of escalating rarity as floors climb.
    floor_rarity = (
        Rarity.COMMON if floor < 5 else
        Rarity.UNCOMMON if floor < 10 else
        Rarity.RARE if floor < 25 else
        Rarity.EPIC if floor < 50 else
        Rarity.LEGENDARY
    )
    pool = list(db.scalars(select(HeroTemplate).where(HeroTemplate.rarity == floor_rarity)))
    if not pool:
        # Fall back down the ladder.
        for fb in (Rarity.EPIC, Rarity.RARE, Rarity.UNCOMMON, Rarity.COMMON):
            pool = list(db.scalars(select(HeroTemplate).where(HeroTemplate.rarity == fb)))
            if pool:
                break
    units = []
    n = _enemy_count_for_floor(floor)
    lvl = _enemy_level_for_floor(floor)
    for j in range(n):
        tmpl = rng.choice(pool)
        units.append(_unit_from_template(tmpl, lvl, "B", j))
    return units


def _rewards_for_floor(floor: int) -> dict[str, int]:
    rewards = {"coins": 100 * floor}
    if floor % 5 == 0:
        rewards["gems"] = 5 + (floor // 25) * 5  # 5 / 10 / 15... at 25/50
    if floor % 10 == 0:
        rewards["shards"] = 10
    return rewards


class TowerAttemptIn(BaseModel):
    team: list[int] = Field(min_length=1, max_length=3)


@router.get("")
def get_status(
    account: Annotated[Account, Depends(get_current_account)],
) -> dict:
    _reset_season_if_stale(account)
    _reset_daily_if_stale(account)
    floor = int(account.tower_floor or 1)
    return {
        "floor": floor,
        "best_floor": int(account.tower_best_floor or 0),
        "attempts_today": int(account.tower_attempts_today or 0),
        "attempts_max": DAILY_ATTEMPTS,
        "attempts_remaining": max(0, DAILY_ATTEMPTS - int(account.tower_attempts_today or 0)),
        "season_key": account.tower_season_key or _current_season_key(),
        "next_floor_preview": {
            "floor": floor,
            "enemy_count": _enemy_count_for_floor(floor),
            "enemy_level": _enemy_level_for_floor(floor),
            "rewards": _rewards_for_floor(floor),
        },
    }


@router.post("/attempt", status_code=status.HTTP_201_CREATED)
def attempt_floor(
    body: TowerAttemptIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    _reset_season_if_stale(account)
    _reset_daily_if_stale(account)
    if (account.tower_attempts_today or 0) >= DAILY_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily attempt cap reached")

    # Validate team ownership.
    heroes = [db.get(HeroInstance, hid) for hid in body.team]
    for hid, h in zip(body.team, heroes):
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")

    floor = int(account.tower_floor or 1)
    rng = random.Random()
    team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(heroes)]
    team_b = _build_enemy_team(db, floor, rng)

    account.tower_attempts_today = int(account.tower_attempts_today or 0) + 1
    result = simulate(team_a, team_b, rng)
    won = result.outcome == "WIN"
    granted: dict[str, int] = {}
    if won:
        rewards = _rewards_for_floor(floor)
        granted = dict(rewards)
        if rewards.get("coins"):
            account.coins = int(account.coins or 0) + rewards["coins"]
        if rewards.get("gems"):
            account.gems = int(account.gems or 0) + rewards["gems"]
        if rewards.get("shards"):
            account.shards = int(account.shards or 0) + rewards["shards"]
        account.tower_floor = floor + 1
        if (account.tower_floor or 1) > int(account.tower_best_floor or 0):
            account.tower_best_floor = account.tower_floor

    db.commit()
    return {
        "won": won,
        "floor_attempted": floor,
        "floor_after": int(account.tower_floor or 1),
        "best_floor": int(account.tower_best_floor or 0),
        "attempts_remaining": max(0, DAILY_ATTEMPTS - int(account.tower_attempts_today or 0)),
        "rewards": granted,
        "log_summary": {
            "outcome": result.outcome,
            "turns": getattr(result, "turns", None),
        },
    }


@router.get("/leaderboard")
def leaderboard(
    db: Annotated[Session, Depends(get_db)],
    limit: int = 25,
) -> list[dict]:
    rows = db.query(Account).order_by(
        desc(Account.tower_best_floor),
        desc(Account.tower_floor),
    ).limit(limit).all()
    return [
        {
            "account_id": a.id,
            "best_floor": int(a.tower_best_floor or 0),
            "current_floor": int(a.tower_floor or 1),
        }
        for a in rows if (a.tower_best_floor or 0) > 0
    ]
