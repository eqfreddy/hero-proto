"""Achievements catalog + per-account unlock state.

Catalog is content-as-code (this file). Per-account state lives on
`Account.achievements_json` as a dict {code: iso_unlock_timestamp}.

Auto-checks fire from activity routers via `check_achievements()`. Each
achievement has a `condition(db, account) -> bool` predicate; if it's
True and the code isn't already unlocked, we unlock + grant the reward.

To add a new achievement: append to the ACHIEVEMENTS list. Define a code,
display fields, the predicate, and the reward dict (same shape as shop
contents). Re-run the test suite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    Battle,
    BattleOutcome,
    GachaRecord,
    Gear,
    GuildMember,
    HeroInstance,
    Rarity,
    RaidAttempt,
    utcnow,
)


# --- Predicate helpers — small composable building blocks --------------------


def _summon_count(db: Session, account: Account) -> int:
    return db.scalar(
        select(func.count(GachaRecord.id)).where(GachaRecord.account_id == account.id)
    ) or 0


def _battle_win_count(db: Session, account: Account) -> int:
    return db.scalar(
        select(func.count(Battle.id)).where(
            Battle.account_id == account.id,
            Battle.outcome == BattleOutcome.WIN,
        )
    ) or 0


def _hero_count(db: Session, account: Account) -> int:
    return db.scalar(
        select(func.count(HeroInstance.id)).where(HeroInstance.account_id == account.id)
    ) or 0


def _gear_count(db: Session, account: Account) -> int:
    return db.scalar(
        select(func.count(Gear.id)).where(Gear.account_id == account.id)
    ) or 0


def _has_rarity(db: Session, account: Account, rarity: Rarity) -> bool:
    return db.scalar(
        select(GachaRecord.id).where(
            GachaRecord.account_id == account.id,
            GachaRecord.rarity == rarity,
        ).limit(1)
    ) is not None


def _max_stars(db: Session, account: Account) -> int:
    return int(db.scalar(
        select(func.max(HeroInstance.stars)).where(HeroInstance.account_id == account.id)
    ) or 0)


def _has_guild(db: Session, account: Account) -> bool:
    return db.get(GuildMember, account.id) is not None


def _raid_attack_count(db: Session, account: Account) -> int:
    return db.scalar(
        select(func.count(RaidAttempt.id)).where(RaidAttempt.account_id == account.id)
    ) or 0


def _stages_cleared_count(account: Account) -> int:
    try:
        return len(json.loads(account.stages_cleared_json or "[]"))
    except json.JSONDecodeError:
        return 0


# --- Catalog -----------------------------------------------------------------


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    description: str
    icon: str
    condition: Callable[[Session, Account], bool]
    reward: dict  # {gems, shards, coins, access_cards, free_summon_credits}


ACHIEVEMENTS: list[Achievement] = [
    # First-session milestones
    Achievement(
        code="first_summon",
        title="First Pull",
        description="Open your first summon. The dopamine begins.",
        icon="🎰",
        condition=lambda db, a: _summon_count(db, a) >= 1,
        reward={"gems": 25},
    ),
    Achievement(
        code="first_win",
        title="First Blood",
        description="Win your first battle. The Ticket Gremlin remembers.",
        icon="⚔️",
        condition=lambda db, a: _battle_win_count(db, a) >= 1,
        reward={"coins": 100},
    ),
    Achievement(
        code="join_guild",
        title="Found Your People",
        description="Join (or create) a guild.",
        icon="🏰",
        condition=lambda db, a: _has_guild(db, a),
        reward={"gems": 30, "coins": 200},
    ),
    Achievement(
        code="tutorial_done",
        title="Day 1 Onboarding",
        description="Clear the tutorial stage.",
        icon="📋",
        condition=lambda db, a: "tutorial_first_ticket" in (
            json.loads(a.stages_cleared_json or "[]") if isinstance(a.stages_cleared_json, str) else []
        ),
        reward={"shards": 5},
    ),

    # Roster size
    Achievement(
        code="roster_10",
        title="A Whole Team",
        description="Own 10 heroes.",
        icon="🧑‍🤝‍🧑",
        condition=lambda db, a: _hero_count(db, a) >= 10,
        reward={"shards": 10, "coins": 200},
    ),
    Achievement(
        code="roster_50",
        title="HR Nightmare",
        description="Own 50 heroes.",
        icon="🗂️",
        condition=lambda db, a: _hero_count(db, a) >= 50,
        reward={"gems": 100, "shards": 30},
    ),

    # Rarity unlocks
    Achievement(
        code="first_rare",
        title="Tier Unlocked: RARE",
        description="Pull your first RARE+.",
        icon="🥉",
        condition=lambda db, a: _has_rarity(db, a, Rarity.RARE),
        reward={"shards": 5},
    ),
    Achievement(
        code="first_epic",
        title="Tier Unlocked: EPIC",
        description="Pull your first EPIC. The pity counter is reset.",
        icon="🥈",
        condition=lambda db, a: _has_rarity(db, a, Rarity.EPIC),
        reward={"gems": 50, "shards": 15},
    ),
    Achievement(
        code="first_legendary",
        title="Tier Unlocked: LEGENDARY",
        description="Pull your first LEGENDARY. The Founder weeps.",
        icon="🥇",
        condition=lambda db, a: _has_rarity(db, a, Rarity.LEGENDARY),
        reward={"gems": 200, "free_summon_credits": 1},
    ),
    Achievement(
        code="first_myth",
        title="Tier Unlocked: MYTH",
        description="Pull a MYTH-tier hero. Reality bends.",
        icon="🌟",
        condition=lambda db, a: _has_rarity(db, a, Rarity.MYTH),
        reward={"gems": 500, "free_summon_credits": 3, "access_cards": 5},
    ),

    # Ascension milestones
    Achievement(
        code="first_3star",
        title="Ascended",
        description="Reach 3★ on any hero.",
        icon="⭐",
        condition=lambda db, a: _max_stars(db, a) >= 3,
        reward={"shards": 20},
    ),
    Achievement(
        code="first_5star",
        title="Maximum Burnout",
        description="Reach 5★ on any hero. They've seen things.",
        icon="🌟",
        condition=lambda db, a: _max_stars(db, a) >= 5,
        reward={"gems": 200, "free_summon_credits": 1},
    ),

    # Battle volume
    Achievement(
        code="wins_10",
        title="Just Doing My Job",
        description="Win 10 battles.",
        icon="🛡️",
        condition=lambda db, a: _battle_win_count(db, a) >= 10,
        reward={"coins": 500, "shards": 5},
    ),
    Achievement(
        code="wins_100",
        title="Crushing It",
        description="Win 100 battles.",
        icon="⚔️",
        condition=lambda db, a: _battle_win_count(db, a) >= 100,
        reward={"gems": 100, "shards": 30},
    ),
    Achievement(
        code="wins_1000",
        title="Vested",
        description="Win 1,000 battles. You should probably take a break.",
        icon="🏆",
        condition=lambda db, a: _battle_win_count(db, a) >= 1000,
        reward={"gems": 500, "free_summon_credits": 5, "access_cards": 10},
    ),

    # Stage progression
    Achievement(
        code="stages_5",
        title="Five Stages of Grief",
        description="Clear 5 stages.",
        icon="📈",
        condition=lambda db, a: _stages_cleared_count(a) >= 5,
        reward={"coins": 300},
    ),
    Achievement(
        code="stages_15",
        title="Quarterly Review",
        description="Clear 15 stages.",
        icon="📊",
        condition=lambda db, a: _stages_cleared_count(a) >= 15,
        reward={"gems": 75, "shards": 20},
    ),

    # Raids
    Achievement(
        code="raid_1",
        title="Took a Swing",
        description="Land your first raid attack.",
        icon="🐉",
        condition=lambda db, a: _raid_attack_count(db, a) >= 1,
        reward={"shards": 5},
    ),
    Achievement(
        code="raid_25",
        title="Guild Carry",
        description="Land 25 raid attacks.",
        icon="🐲",
        condition=lambda db, a: _raid_attack_count(db, a) >= 25,
        reward={"gems": 100, "access_cards": 3},
    ),

    # Gear collection
    Achievement(
        code="gear_25",
        title="Inventory Hoarder",
        description="Own 25 gear items.",
        icon="⚙️",
        condition=lambda db, a: _gear_count(db, a) >= 25,
        reward={"coins": 400},
    ),

    # Summon volume
    Achievement(
        code="summons_50",
        title="Pity Touched",
        description="Open 50 summons (you're due an EPIC by now).",
        icon="🎲",
        condition=lambda db, a: _summon_count(db, a) >= 50,
        reward={"shards": 25},
    ),
    Achievement(
        code="summons_500",
        title="Whale Adjacent",
        description="Open 500 summons. The gacha gods know your name.",
        icon="🐋",
        condition=lambda db, a: _summon_count(db, a) >= 500,
        reward={"gems": 250, "free_summon_credits": 5},
    ),
]

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS}


# --- Per-account unlock state -----------------------------------------------


def _unlocked(account: Account) -> dict[str, str]:
    try:
        data = json.loads(account.achievements_json or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_unlocked(account: Account, unlocked: dict[str, str]) -> None:
    account.achievements_json = json.dumps(unlocked, separators=(",", ":"))


def is_unlocked(account: Account, code: str) -> bool:
    return code in _unlocked(account)


def unlock_progress(db: Session, account: Account) -> list[dict]:
    """Catalog joined with per-account unlocked state. Used by the UI."""
    unlocked = _unlocked(account)
    out = []
    for ach in ACHIEVEMENTS:
        out.append({
            "code": ach.code,
            "title": ach.title,
            "description": ach.description,
            "icon": ach.icon,
            "reward": dict(ach.reward),
            "unlocked": ach.code in unlocked,
            "unlocked_at": unlocked.get(ach.code, ""),
        })
    return out


# --- Auto-check + grant -----------------------------------------------------


_GRANTABLE_KINDS = ("gems", "shards", "coins", "access_cards", "free_summon_credits")


def _grant_reward(account: Account, reward: dict) -> dict:
    granted: dict = {}
    for kind in _GRANTABLE_KINDS:
        amount = int(reward.get(kind, 0) or 0)
        if amount <= 0:
            continue
        setattr(account, kind, (getattr(account, kind) or 0) + amount)
        granted[kind] = amount
    return granted


def check_achievements(db: Session, account: Account) -> list[dict]:
    """Run every achievement predicate. Unlock and grant rewards for any
    that are newly satisfied. Returns a list of {code, title, granted}
    dicts for anything unlocked this call (empty if none).

    Designed to be cheap to call on every activity hook — the predicate
    pool is small (<30) and most short-circuit on a single counter query.
    """
    newly: list[dict] = []
    unlocked = _unlocked(account)
    changed = False

    for ach in ACHIEVEMENTS:
        if ach.code in unlocked:
            continue
        try:
            if not ach.condition(db, account):
                continue
        except Exception:
            # A bad predicate must not break the request — log + skip.
            import logging
            logging.getLogger("achievements").exception(
                "predicate %r raised", ach.code,
            )
            continue
        granted = _grant_reward(account, ach.reward)
        unlocked[ach.code] = utcnow().isoformat()
        changed = True
        newly.append({
            "code": ach.code,
            "title": ach.title,
            "icon": ach.icon,
            "granted": granted,
        })

    if changed:
        _save_unlocked(account, unlocked)
        # Drop one notification per unlock so the bell fires.
        from app.notifications import notify as _notify
        for unlock in newly:
            grant_bits = []
            for k, v in (unlock.get("granted") or {}).items():
                if isinstance(v, int) and v > 0:
                    grant_bits.append(f"+{v} {k.replace('_', ' ')}")
            body = "Reward: " + ", ".join(grant_bits) if grant_bits else ""
            _notify(
                db, account,
                kind="achievement",
                title=f"Achievement unlocked: {unlock['title']}",
                body=body,
                link="/app/partials/achievements",
                icon=unlock.get("icon", "🏆"),
            )
    return newly
