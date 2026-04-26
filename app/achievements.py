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
    # Phase 2 polish — optional progress getter for "do X N times" goals.
    # Returns (current, target). When provided, the UI renders a
    # progress bar instead of just a locked icon. Achievements without
    # this stay binary (existence-style: "have at least one EPIC").
    progress: Callable[[Session, Account], tuple[int, int]] | None = None


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
        progress=lambda db, a: (_hero_count(db, a), 10),
    ),
    Achievement(
        code="roster_50",
        title="HR Nightmare",
        description="Own 50 heroes.",
        icon="🗂️",
        condition=lambda db, a: _hero_count(db, a) >= 50,
        reward={"gems": 100, "shards": 30},
        progress=lambda db, a: (_hero_count(db, a), 50),
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
        progress=lambda db, a: (_battle_win_count(db, a), 10),
    ),
    Achievement(
        code="wins_100",
        title="Crushing It",
        description="Win 100 battles.",
        icon="⚔️",
        condition=lambda db, a: _battle_win_count(db, a) >= 100,
        reward={"gems": 100, "shards": 30},
        progress=lambda db, a: (_battle_win_count(db, a), 100),
    ),
    Achievement(
        code="wins_1000",
        title="Vested",
        description="Win 1,000 battles. You should probably take a break.",
        icon="🏆",
        condition=lambda db, a: _battle_win_count(db, a) >= 1000,
        reward={"gems": 500, "free_summon_credits": 5, "access_cards": 10},
        progress=lambda db, a: (_battle_win_count(db, a), 1000),
    ),

    # Stage progression
    Achievement(
        code="stages_5",
        title="Five Stages of Grief",
        description="Clear 5 stages.",
        icon="📈",
        condition=lambda db, a: _stages_cleared_count(a) >= 5,
        reward={"coins": 300},
        progress=lambda db, a: (_stages_cleared_count(a), 5),
    ),
    Achievement(
        code="stages_15",
        title="Quarterly Review",
        description="Clear 15 stages.",
        icon="📊",
        condition=lambda db, a: _stages_cleared_count(a) >= 15,
        reward={"gems": 75, "shards": 20},
        progress=lambda db, a: (_stages_cleared_count(a), 15),
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
        progress=lambda db, a: (_raid_attack_count(db, a), 25),
    ),

    # Gear collection
    Achievement(
        code="gear_25",
        title="Inventory Hoarder",
        description="Own 25 gear items.",
        icon="⚙️",
        condition=lambda db, a: _gear_count(db, a) >= 25,
        reward={"coins": 400},
        progress=lambda db, a: (_gear_count(db, a), 25),
    ),

    # Summon volume
    Achievement(
        code="summons_50",
        title="Pity Touched",
        description="Open 50 summons (you're due an EPIC by now).",
        icon="🎲",
        condition=lambda db, a: _summon_count(db, a) >= 50,
        reward={"shards": 25},
        progress=lambda db, a: (_summon_count(db, a), 50),
    ),
    Achievement(
        code="summons_500",
        title="Whale Adjacent",
        description="Open 500 summons. The gacha gods know your name.",
        icon="🐋",
        condition=lambda db, a: _summon_count(db, a) >= 500,
        reward={"gems": 250, "free_summon_credits": 5},
        progress=lambda db, a: (_summon_count(db, a), 500),
    ),
]

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS}


# --- Hardcore tier (Phase 3 teaser) ----------------------------------------
#
# Locked-but-visible long-tail goals. No real predicates wired yet — these
# render as `?` lock icons in the UI to give players something to chase.
# Concrete predicates land alongside the level-50 alignment fork (Phase 3.5)
# when Hardcore mode itself is shipped.

HARDCORE_ACHIEVEMENTS: list[dict] = [
    {
        "code": "hc_no_deaths_chapter",
        "title": "Untouched",
        "description": "Clear an entire story chapter without losing a single hero in any battle.",
        "icon": "💀",
        "reward_preview": "+1000 gems · cosmetic frame",
    },
    {
        "code": "hc_solo_tutorial",
        "title": "Solo Run",
        "description": "Beat the tutorial with only 1 hero alive at the end.",
        "icon": "🎯",
        "reward_preview": "+500 gems",
    },
    {
        "code": "hc_arena_top_1pct",
        "title": "Top 1%",
        "description": "Reach the top 1% of arena ratings during a season window.",
        "icon": "👑",
        "reward_preview": "+5000 gems · alignment-exclusive frame",
    },
    {
        "code": "hc_full_collection",
        "title": "Completionist",
        "description": "Own at least one copy of every non-event hero template.",
        "icon": "📖",
        "reward_preview": "+2000 gems · 5 access cards",
    },
    {
        "code": "hc_max_synergy_win",
        "title": "Faction Loyalist",
        "description": "Win 50 battles with full 5-of-faction team synergy.",
        "icon": "⚜️",
        "reward_preview": "+1500 gems · faction title",
    },
    {
        "code": "hc_5star_team",
        "title": "All-Stars",
        "description": "Field a full team of 5★ heroes in a winning campaign battle.",
        "icon": "⭐",
        "reward_preview": "+2500 gems · stash expansion",
    },
    {
        "code": "hc_no_gear",
        "title": "Naked & Afraid",
        "description": "Win 10 HARD-tier stages with no gear equipped on any team member.",
        "icon": "🩲",
        "reward_preview": "+1000 gems · cosmetic taunt",
    },
    {
        "code": "hc_speedrun_chapter",
        "title": "Outage Response",
        "description": "Clear all 5 stages of a chapter in under 60 minutes total.",
        "icon": "⚡",
        "reward_preview": "+1500 gems · time-attack frame",
    },
]


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
    """Catalog joined with per-account unlocked state. Used by the UI.

    Phase 2 polish — when the achievement carries a `progress` getter,
    we surface (current, target) so the UI can render a "47 / 100"
    label + progress bar on locked entries. Achievements without it
    stay binary.
    """
    unlocked = _unlocked(account)
    out = []
    for ach in ACHIEVEMENTS:
        is_unlocked = ach.code in unlocked
        cur, tgt = 0, 0
        if ach.progress is not None and not is_unlocked:
            try:
                cur, tgt = ach.progress(db, account)
                cur = int(cur or 0)
                tgt = int(tgt or 0)
                # Clamp display: a player at 47 with target 100 reads
                # "47 / 100"; cap displayed cur at target so we never
                # show "120 / 100" if a counter races past the gate
                # before check_achievements caught up.
                cur = min(cur, tgt) if tgt > 0 else cur
            except Exception:
                cur, tgt = 0, 0
        out.append({
            "code": ach.code,
            "title": ach.title,
            "description": ach.description,
            "icon": ach.icon,
            "reward": dict(ach.reward),
            "unlocked": is_unlocked,
            "unlocked_at": unlocked.get(ach.code, ""),
            "progress_current": cur,
            "progress_target": tgt,
            "has_progress": tgt > 0,
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
