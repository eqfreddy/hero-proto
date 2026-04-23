"""Daily-quest rotation + progress helpers.

Daily quests reset at UTC midnight. Each day a player sees up to 3 active quests.
If they open the app on a new day, we lazily roll a new set.
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    DailyQuest,
    DailyQuestKind,
    DailyQuestStatus,
    Stage,
    utcnow,
)


DAILY_SLOT_COUNT = 3


def day_key(dt: datetime | None = None) -> str:
    dt = dt or utcnow()
    return dt.strftime("%Y-%m-%d")


# Templates of daily quests. The rotator picks 3 at random per day.
# Rewards chosen to be meaningful but not free LEGENDARYs.
TEMPLATES: list[dict] = [
    {"kind": DailyQuestKind.WIN_BATTLES, "goal": 3, "reward_coins": 200, "reward_gems": 10},
    {"kind": DailyQuestKind.WIN_BATTLES, "goal": 5, "reward_coins": 350, "reward_gems": 15, "reward_shards": 1},
    {"kind": DailyQuestKind.SUMMON_HEROES, "goal": 3, "reward_coins": 150, "reward_gems": 5},
    {"kind": DailyQuestKind.SUMMON_HEROES, "goal": 10, "reward_coins": 500, "reward_gems": 20, "reward_shards": 2},
    {"kind": DailyQuestKind.ARENA_ATTACKS, "goal": 2, "reward_coins": 200, "reward_gems": 15},
    {"kind": DailyQuestKind.CLEAR_STAGE_X, "goal": 1, "target": "onboarding_day", "reward_coins": 100, "reward_gems": 5},
    {"kind": DailyQuestKind.CLEAR_STAGE_X, "goal": 1, "target": "first_outage", "reward_coins": 150, "reward_gems": 10},
]


def _pick_target_code(db: Session, kind: DailyQuestKind, target: str | None) -> str:
    if kind != DailyQuestKind.CLEAR_STAGE_X:
        return ""
    if target is not None:
        return target
    # Fallback: pick the first unlocked stage.
    s = db.scalar(select(Stage).order_by(Stage.order))
    return s.code if s else ""


def _roll_daily_set(db: Session, account: Account, key: str, rng: random.Random) -> list[DailyQuest]:
    rng.shuffle(pool := list(TEMPLATES))
    chosen = pool[:DAILY_SLOT_COUNT]
    quests: list[DailyQuest] = []
    for t in chosen:
        kind = t["kind"]
        target = t.get("target")
        q = DailyQuest(
            account_id=account.id,
            day_key=key,
            kind=kind,
            target_key=_pick_target_code(db, kind, target),
            goal=int(t["goal"]),
            progress=0,
            reward_gems=int(t.get("reward_gems", 0)),
            reward_coins=int(t.get("reward_coins", 0)),
            reward_shards=int(t.get("reward_shards", 0)),
        )
        db.add(q)
        quests.append(q)
    db.flush()
    return quests


def ensure_today(db: Session, account: Account) -> list[DailyQuest]:
    """Return today's quests, creating them if none exist yet for the current UTC day."""
    key = day_key()
    todays = list(
        db.scalars(
            select(DailyQuest).where(
                DailyQuest.account_id == account.id,
                DailyQuest.day_key == key,
            )
        )
    )
    if todays:
        return todays
    rng = random.Random(f"{account.id}:{key}")
    return _roll_daily_set(db, account, key, rng)


def _progress_kind(
    db: Session,
    account: Account,
    kind: DailyQuestKind,
    amount: int = 1,
    target_key: str | None = None,
) -> list[DailyQuest]:
    """Advance all ACTIVE quests of this kind (optionally gated on target_key)."""
    quests = ensure_today(db, account)
    completed: list[DailyQuest] = []
    for q in quests:
        if q.status != DailyQuestStatus.ACTIVE:
            continue
        if q.kind != kind:
            continue
        if target_key is not None and q.target_key and q.target_key != target_key:
            continue
        q.progress = min(q.goal, q.progress + amount)
        if q.progress >= q.goal:
            q.status = DailyQuestStatus.COMPLETE
            q.completed_at = utcnow()
            completed.append(q)
    return completed


def on_battle_won(db: Session, account: Account, stage_code: str) -> list[DailyQuest]:
    done: list[DailyQuest] = []
    done += _progress_kind(db, account, DailyQuestKind.WIN_BATTLES)
    done += _progress_kind(db, account, DailyQuestKind.CLEAR_STAGE_X, target_key=stage_code)
    return done


def on_summon(db: Session, account: Account, count: int = 1) -> list[DailyQuest]:
    return _progress_kind(db, account, DailyQuestKind.SUMMON_HEROES, amount=count)


def on_arena_attack(db: Session, account: Account) -> list[DailyQuest]:
    return _progress_kind(db, account, DailyQuestKind.ARENA_ATTACKS)
