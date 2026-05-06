"""Static quest definitions and DB seeding.

seed_quests(db) is called once at startup — it upserts the onboarding quest
definition so content changes deploy without a manual migration.

auto_enroll(db, account) is called after every new registration to create
the AccountQuest row. Idempotent — silently no-ops if the row already exists.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models import Account, AccountQuest, Quest

log = logging.getLogger(__name__)

ONBOARDING_QUEST_ID = "onboarding_week_one"

_TASKS = [
    {"id": "first_battle",       "label": "Run your first battle",                   "event": "BATTLE_COMPLETE",        "target": 1},
    {"id": "first_summon",       "label": "Summon a hero",                            "event": "SUMMON_COMPLETE",        "target": 1},
    {"id": "first_gear",         "label": "Equip a gear item",                        "event": "GEAR_EQUIPPED",          "target": 1},
    {"id": "faction_chosen",     "label": "Choose your faction",                      "event": "FACTION_CHOSEN",         "target": 1},
    {"id": "win_5",              "label": "Win 5 battles",                             "event": "BATTLE_WIN",             "target": 5},
    {"id": "story_chapter_1",    "label": "Clear a story chapter",                    "event": "STORY_CHAPTER_CLEARED",  "target": 1},
    {"id": "first_arena_win",    "label": "Win your first arena match",               "event": "ARENA_WIN",              "target": 1},
    {"id": "guild_joined",       "label": "Join a guild",                             "event": "GUILD_JOINED",           "target": 1},
    {"id": "account_level_5",    "label": "Reach account level 5",                   "event": "ACCOUNT_LEVEL_REACHED",  "target": 5},
    {"id": "first_daily",        "label": "Complete a daily quest",                   "event": "DAILY_QUEST_COMPLETE",   "target": 1},
    {"id": "raid_contributed",   "label": "Contribute to a guild raid",               "event": "RAID_CONTRIBUTED",       "target": 1},
    {"id": "hard_stage",         "label": "Clear a Hard difficulty stage",            "event": "HARD_STAGE_CLEARED",     "target": 1},
    {"id": "hero_level_5",       "label": "Level a hero to level 5",                 "event": "HERO_LEVELED",           "target": 5},
    {"id": "daily_3_days",       "label": "Complete daily quests on 3 separate days", "event": "DAILY_QUEST_COMPLETE",  "target": 3},
    {"id": "account_level_10",   "label": "Reach account level 10",                  "event": "ACCOUNT_LEVEL_REACHED",  "target": 10},
    {"id": "win_10_arena",       "label": "Win 10 arena matches total",               "event": "ARENA_WIN",              "target": 10},
    {"id": "story_3_chapters",   "label": "Complete 3 story chapters",               "event": "STORY_CHAPTER_CLEARED",  "target": 3},
    {"id": "story_arc_1",        "label": "Complete the first story arc",             "event": "STORY_ARC_CLEARED",      "target": 1},
    {"id": "legendary_stage",    "label": "Clear a Legendary stage",                 "event": "LEGENDARY_STAGE_CLEARED","target": 1},
]

_REWARD = {
    "cosmetic_frame": "survived_onboarding",
    "choice": [
        {"id": "epic",  "label": "Guaranteed Epic hero",  "description": "One named Epic hero summon — no gacha"},
        {"id": "gems",  "label": "500 Gems",              "description": "Premium currency, spend anywhere"},
    ],
}

_QUEST_DEF = {
    "id": ONBOARDING_QUEST_ID,
    "name": "Getting Started",
    "description": "Welcome to the corp. Here's what we need you to do before Friday.",
    "tasks": _TASKS,
    "reward": _REWARD,
    "sort_order": 0,
}


def seed_quests(db: Session) -> None:
    """Upsert the static quest definitions. Called from lifespan startup."""
    existing = db.get(Quest, ONBOARDING_QUEST_ID)
    if existing is None:
        q = Quest(
            id=_QUEST_DEF["id"],
            name=_QUEST_DEF["name"],
            description=_QUEST_DEF["description"],
            tasks_json=json.dumps(_QUEST_DEF["tasks"]),
            reward_json=json.dumps(_QUEST_DEF["reward"]),
            sort_order=_QUEST_DEF["sort_order"],
        )
        db.add(q)
    else:
        existing.name = _QUEST_DEF["name"]
        existing.description = _QUEST_DEF["description"]
        existing.tasks_json = json.dumps(_QUEST_DEF["tasks"])
        existing.reward_json = json.dumps(_QUEST_DEF["reward"])
        existing.sort_order = _QUEST_DEF["sort_order"]
    db.commit()
    log.info("quest seed complete")


def auto_enroll(db: Session, account: Account) -> None:
    """Enroll a new account in the onboarding quest. Idempotent.
    Flushes but does NOT commit — caller is responsible for the transaction."""
    if db.get(Quest, ONBOARDING_QUEST_ID) is None:
        log.warning("auto_enroll skipped — quest %s not seeded yet", ONBOARDING_QUEST_ID)
        return
    existing = (
        db.query(AccountQuest)
        .filter_by(account_id=account.id, quest_id=ONBOARDING_QUEST_ID)
        .first()
    )
    if existing is not None:
        return
    aq = AccountQuest(account_id=account.id, quest_id=ONBOARDING_QUEST_ID)
    db.add(aq)
    db.flush()
