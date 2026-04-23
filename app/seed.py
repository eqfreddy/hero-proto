"""Seed hero templates + campaign stages.

Run with:
    uv run python -m app.seed
"""

from __future__ import annotations

import json

from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Faction,
    HeroTemplate,
    LiveOpsEvent,
    LiveOpsKind,
    Rarity,
    Role,
    Stage,
    utcnow,
)


def _ensure_schema() -> None:
    ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


# --- Hero templates ----------------------------------------------------------

HERO_SEEDS: list[dict] = [
    # --- COMMON ---
    {
        "code": "ticket_gremlin",
        "name": "Ticket Gremlin",
        "rarity": Rarity.COMMON, "faction": Faction.HELPDESK, "role": Role.ATK,
        "base_hp": 800, "base_atk": 90, "base_def": 60, "base_spd": 95,
        "basic_mult": 1.0, "special": None, "special_cooldown": 0,
    },
    {
        "code": "printer_whisperer",
        "name": "Printer Whisperer",
        "rarity": Rarity.COMMON, "faction": Faction.HELPDESK, "role": Role.SUP,
        "base_hp": 900, "base_atk": 70, "base_def": 70, "base_spd": 90,
        "basic_mult": 0.8,
        "special": {
            "name": "PEBKAC Pep-Talk", "type": "BUFF",
            "target": "ally_lowest_hp",
            "effect": {"kind": "ATK_UP", "turns": 2, "value": 0.2},
        },
        "special_cooldown": 3,
    },
    {
        "code": "overnight_janitor",
        "name": "Overnight Janitor",
        "rarity": Rarity.COMMON, "faction": Faction.LEGACY, "role": Role.DEF,
        "base_hp": 1400, "base_atk": 55, "base_def": 120, "base_spd": 75,
        "basic_mult": 0.7,
        "special": {
            "name": "Mop Stance", "type": "SHIELD",
            "target": "self",
        },
        "special_cooldown": 4,
    },

    # --- UNCOMMON ---
    {
        "code": "jaded_intern",
        "name": "Jaded Intern",
        "rarity": Rarity.UNCOMMON, "faction": Faction.HELPDESK, "role": Role.ATK,
        "base_hp": 900, "base_atk": 110, "base_def": 55, "base_spd": 100,
        "basic_mult": 1.0,
        "special": {
            "name": "Passive-Aggressive Note", "type": "DAMAGE",
            "mult": 1.4, "target": "enemy_lowest_hp",
            "effect": {"kind": "POISON", "turns": 2, "value": 0.1},
        },
        "special_cooldown": 3,
    },
    {
        "code": "sre_on_call",
        "name": "SRE on Call",
        "rarity": Rarity.UNCOMMON, "faction": Faction.DEVOPS, "role": Role.SUP,
        "base_hp": 1000, "base_atk": 75, "base_def": 80, "base_spd": 105,
        "basic_mult": 0.8,
        "special": {
            "name": "Runbook", "type": "CLEANSE",
            "target": "ally_lowest_hp", "heal_frac": 0.25,
        },
        "special_cooldown": 4,
    },
    {
        "code": "compliance_officer",
        "name": "Compliance Officer",
        "rarity": Rarity.UNCOMMON, "faction": Faction.EXECUTIVE, "role": Role.DEF,
        "base_hp": 1500, "base_atk": 70, "base_def": 130, "base_spd": 80,
        "basic_mult": 0.9,
        "special": {
            "name": "Cite the Policy", "type": "DEBUFF",
            "target": "enemy_lowest_hp",
            "effect": {"kind": "DEF_DOWN", "turns": 2, "value": 0.3},
        },
        "special_cooldown": 3,
    },
    {
        "code": "security_auditor",
        "name": "Security Auditor",
        "rarity": Rarity.UNCOMMON, "faction": Faction.EXECUTIVE, "role": Role.ATK,
        "base_hp": 950, "base_atk": 105, "base_def": 70, "base_spd": 95,
        "basic_mult": 1.0,
        "special": {
            "name": "Mass Pentest", "type": "AOE_DEBUFF",
            "effect": {"kind": "POISON", "turns": 2, "value": 0.08},
        },
        "special_cooldown": 4,
    },

    # --- RARE ---
    {
        "code": "the_sysadmin",
        "name": "The Sysadmin",
        "rarity": Rarity.RARE, "faction": Faction.LEGACY, "role": Role.DEF,
        "base_hp": 1800, "base_atk": 85, "base_def": 150, "base_spd": 85,
        "basic_mult": 1.0,
        "special": {
            "name": "sudo !!", "type": "SHIELD",
            "target": "self",
            "self_effect": {"kind": "DEF_DOWN", "turns": 0, "value": 0.0},
        },
        "special_cooldown": 4,
    },
    {
        "code": "root_access_janitor",
        "name": "Root-Access Janitor",
        "rarity": Rarity.RARE, "faction": Faction.ROGUE_IT, "role": Role.ATK,
        "base_hp": 1100, "base_atk": 135, "base_def": 75, "base_spd": 115,
        "basic_mult": 1.0,
        "special": {
            "name": "Mop of Regrets", "type": "DAMAGE",
            "mult": 1.8, "target": "enemy_lowest_hp",
            "effect": {"kind": "STUN", "turns": 1, "value": 1.0},
        },
        "special_cooldown": 4,
    },
    {
        "code": "vp_of_vibes",
        "name": "VP of Vibes",
        "rarity": Rarity.RARE, "faction": Faction.EXECUTIVE, "role": Role.SUP,
        "base_hp": 1200, "base_atk": 80, "base_def": 90, "base_spd": 120,
        "basic_mult": 0.8,
        "special": {
            "name": "All-Hands Hype", "type": "AOE_BUFF",
            "effect": {"kind": "ATK_UP", "turns": 2, "value": 0.25},
        },
        "special_cooldown": 4,
    },
    {
        "code": "keymaster_gary",
        "name": "Keymaster (Gary)",
        "rarity": Rarity.RARE, "faction": Faction.HELPDESK, "role": Role.ATK,
        "base_hp": 1250, "base_atk": 150, "base_def": 80, "base_spd": 105,
        "basic_mult": 1.1,
        "special": {
            "name": "I AM the Keymaster", "type": "DAMAGE",
            "mult": 2.4, "target": "enemy_lowest_hp",
        },
        "special_cooldown": 4,
    },

    # --- EPIC ---
    {
        "code": "the_post_mortem",
        "name": "The Post-Mortem",
        "rarity": Rarity.EPIC, "faction": Faction.DEVOPS, "role": Role.SUP,
        "base_hp": 1400, "base_atk": 95, "base_def": 110, "base_spd": 110,
        "basic_mult": 0.9,
        "special": {
            "name": "Five Whys", "type": "REVIVE",
            "frac": 0.35,
        },
        "special_cooldown": 6,
    },
    {
        "code": "midnight_pager",
        "name": "Midnight Pager",
        "rarity": Rarity.EPIC, "faction": Faction.DEVOPS, "role": Role.ATK,
        "base_hp": 1350, "base_atk": 165, "base_def": 85, "base_spd": 125,
        "basic_mult": 1.0,
        "special": {
            "name": "3AM Escalation", "type": "DAMAGE",
            "mult": 2.4, "hits": 3, "target": "enemy_lowest_hp",
        },
        "special_cooldown": 4,
    },
    {
        "code": "the_consultant",
        "name": "The Consultant",
        "rarity": Rarity.EPIC, "faction": Faction.EXECUTIVE, "role": Role.DEF,
        "base_hp": 2000, "base_atk": 95, "base_def": 180, "base_spd": 95,
        "basic_mult": 0.9,
        "special": {
            "name": "Deliverables Deck", "type": "AOE_DEBUFF",
            "effect": {"kind": "DEF_DOWN", "turns": 2, "value": 0.3},
            "self_effect": {"kind": "SHIELD", "turns": 1, "value": 1.0},
        },
        "special_cooldown": 5,
    },

    # --- LEGENDARY ---
    {
        "code": "the_founder",
        "name": "The Founder",
        "rarity": Rarity.LEGENDARY, "faction": Faction.EXECUTIVE, "role": Role.ATK,
        "base_hp": 1800, "base_atk": 220, "base_def": 110, "base_spd": 130,
        "basic_mult": 1.1,
        "special": {
            "name": "Hostile Takeover", "type": "AOE_DAMAGE",
            "mult": 1.4, "effect": {"kind": "POISON", "turns": 2, "value": 0.1},
        },
        "special_cooldown": 4,
    },
    # --- Expansion 1: filling faction + role gaps ---
    {
        "code": "devops_apprentice",
        "name": "DevOps Apprentice",
        "rarity": Rarity.COMMON, "faction": Faction.DEVOPS, "role": Role.ATK,
        "base_hp": 850, "base_atk": 95, "base_def": 60, "base_spd": 100,
        "basic_mult": 1.0, "special": None, "special_cooldown": 0,
    },
    {
        "code": "forgotten_contractor",
        "name": "Forgotten Contractor",
        "rarity": Rarity.COMMON, "faction": Faction.ROGUE_IT, "role": Role.ATK,
        "base_hp": 900, "base_atk": 100, "base_def": 55, "base_spd": 90,
        "basic_mult": 1.0, "special": None, "special_cooldown": 0,
    },
    {
        "code": "helpdesk_veteran",
        "name": "Helpdesk Veteran",
        "rarity": Rarity.UNCOMMON, "faction": Faction.HELPDESK, "role": Role.DEF,
        "base_hp": 1400, "base_atk": 75, "base_def": 120, "base_spd": 80,
        "basic_mult": 0.9,
        "special": {
            "name": "It's Been Working Fine", "type": "SHIELD", "target": "self",
        },
        "special_cooldown": 3,
    },
    {
        "code": "build_engineer",
        "name": "Build Engineer",
        "rarity": Rarity.UNCOMMON, "faction": Faction.DEVOPS, "role": Role.ATK,
        "base_hp": 980, "base_atk": 115, "base_def": 70, "base_spd": 105,
        "basic_mult": 1.0,
        "special": {
            "name": "Green Build", "type": "DAMAGE",
            "mult": 1.5, "target": "enemy_lowest_hp",
            "effect": {"kind": "ATK_UP", "turns": 2, "value": 0.15},
        },
        "special_cooldown": 3,
    },
    {
        "code": "rogue_dba",
        "name": "Rogue DBA",
        "rarity": Rarity.RARE, "faction": Faction.ROGUE_IT, "role": Role.SUP,
        "base_hp": 1150, "base_atk": 90, "base_def": 85, "base_spd": 115,
        "basic_mult": 0.9,
        "special": {
            "name": "DROP table enemies;", "type": "AOE_DEBUFF",
            "effect": {"kind": "DEF_DOWN", "turns": 2, "value": 0.25},
        },
        "special_cooldown": 4,
    },
    {
        "code": "oncall_warrior",
        "name": "Oncall Warrior",
        "rarity": Rarity.RARE, "faction": Faction.DEVOPS, "role": Role.DEF,
        "base_hp": 1700, "base_atk": 90, "base_def": 140, "base_spd": 95,
        "basic_mult": 1.0,
        "special": {
            "name": "Hold the Pager", "type": "BUFF",
            "target": "self",
            "effect": {"kind": "DEF_DOWN", "turns": 0, "value": 0.0},
            "self_effect": {"kind": "SHIELD", "turns": 1, "value": 1.0},
        },
        "special_cooldown": 3,
    },
    {
        "code": "retired_mainframe_guru",
        "name": "Retired Mainframe Guru",
        "rarity": Rarity.EPIC, "faction": Faction.LEGACY, "role": Role.SUP,
        "base_hp": 1500, "base_atk": 100, "base_def": 115, "base_spd": 115,
        "basic_mult": 0.9,
        "special": {
            "name": "COBOL Incantation", "type": "AOE_BUFF",
            "effect": {"kind": "ATK_UP", "turns": 3, "value": 0.3},
        },
        "special_cooldown": 5,
    },
    {
        "code": "shadow_it_operator",
        "name": "Shadow IT Operator",
        "rarity": Rarity.EPIC, "faction": Faction.ROGUE_IT, "role": Role.ATK,
        "base_hp": 1300, "base_atk": 180, "base_def": 80, "base_spd": 120,
        "basic_mult": 1.0,
        "special": {
            "name": "Unapproved Tool", "type": "DAMAGE",
            "mult": 2.6, "target": "enemy_lowest_hp",
            "effect": {"kind": "POISON", "turns": 3, "value": 0.12},
        },
        "special_cooldown": 4,
    },
    {
        "code": "chaos_monkey",
        "name": "Chaos Monkey",
        "rarity": Rarity.LEGENDARY, "faction": Faction.DEVOPS, "role": Role.ATK,
        "base_hp": 1700, "base_atk": 210, "base_def": 100, "base_spd": 140,
        "basic_mult": 1.1,
        "special": {
            "name": "Random Kill -9", "type": "DAMAGE",
            "mult": 2.8, "hits": 2, "target": "enemy_lowest_hp",
            "effect": {"kind": "STUN", "turns": 1, "value": 1.0},
        },
        "special_cooldown": 4,
    },
    {
        "code": "the_board_member",
        "name": "The Board Member",
        "rarity": Rarity.LEGENDARY, "faction": Faction.EXECUTIVE, "role": Role.SUP,
        "base_hp": 1900, "base_atk": 150, "base_def": 140, "base_spd": 135,
        "basic_mult": 1.0,
        "special": {
            "name": "Strategic Restructure", "type": "CLEANSE",
            "target": "ally_lowest_hp", "heal_frac": 0.5,
        },
        "special_cooldown": 4,
    },
]


# --- Stages ------------------------------------------------------------------


def _wave(enemies: list[tuple[str, int]]) -> dict:
    return {"enemies": [{"template_code": code, "level": level} for code, level in enemies]}


STAGE_SEEDS: list[dict] = [
    {
        "code": "onboarding_day",
        "name": "Onboarding Day",
        "order": 1,
        "energy_cost": 5,
        "recommended_power": 150,
        "coin_reward": 120,
        "first_clear_gems": 25,
        "first_clear_shards": 1,
        "waves": [
            _wave([("ticket_gremlin", 1), ("ticket_gremlin", 1)]),
            _wave([("ticket_gremlin", 1), ("printer_whisperer", 1)]),
        ],
    },
    {
        "code": "first_outage",
        "name": "First Outage",
        "order": 2,
        "energy_cost": 5,
        "recommended_power": 260,
        "coin_reward": 180,
        "first_clear_gems": 25,
        "first_clear_shards": 1,
        "waves": [
            _wave([("ticket_gremlin", 3), ("overnight_janitor", 2), ("ticket_gremlin", 3)]),
            _wave([("printer_whisperer", 4), ("jaded_intern", 3), ("ticket_gremlin", 4)]),
        ],
    },
    {
        "code": "quarterly_audit",
        "name": "Quarterly Audit",
        "order": 3,
        "energy_cost": 6,
        "recommended_power": 420,
        "coin_reward": 240,
        "first_clear_gems": 40,
        "first_clear_shards": 2,
        "waves": [
            _wave([("jaded_intern", 5), ("compliance_officer", 5)]),
            _wave([("security_auditor", 6), ("compliance_officer", 6), ("sre_on_call", 5)]),
            _wave([("jaded_intern", 7), ("security_auditor", 8), ("compliance_officer", 7)]),
        ],
    },
    {
        "code": "legacy_server_room",
        "name": "Legacy Server Room",
        "order": 4,
        "energy_cost": 6,
        "recommended_power": 620,
        "coin_reward": 320,
        "first_clear_gems": 55,
        "first_clear_shards": 2,
        "waves": [
            _wave([("overnight_janitor", 8), ("jaded_intern", 8)]),
            _wave([("compliance_officer", 9), ("overnight_janitor", 9), ("security_auditor", 9)]),
            _wave([("the_sysadmin", 10), ("overnight_janitor", 10)]),
        ],
    },
    {
        "code": "ceos_one_on_one",
        "name": "The CEO's 1:1",
        "order": 5,
        "energy_cost": 8,
        "recommended_power": 900,
        "coin_reward": 500,
        "first_clear_gems": 75,
        "first_clear_shards": 3,
        "waves": [
            _wave([("compliance_officer", 12), ("security_auditor", 12), ("sre_on_call", 12)]),
            _wave([("vp_of_vibes", 13), ("the_sysadmin", 13), ("compliance_officer", 13)]),
            _wave([("the_consultant", 15), ("vp_of_vibes", 14)]),
        ],
    },
    # --- Expansion 1: post-game stages ---
    {
        "code": "reorg_announcement",
        "name": "The Reorg Announcement",
        "order": 6,
        "energy_cost": 9,
        "recommended_power": 1100,
        "coin_reward": 650,
        "first_clear_gems": 90,
        "first_clear_shards": 3,
        "waves": [
            _wave([("security_auditor", 16), ("compliance_officer", 16), ("helpdesk_veteran", 16)]),
            _wave([("build_engineer", 17), ("rogue_dba", 17), ("oncall_warrior", 17)]),
            _wave([("retired_mainframe_guru", 18), ("the_consultant", 18)]),
        ],
    },
    {
        "code": "migration_weekend",
        "name": "Migration Weekend",
        "order": 7,
        "energy_cost": 10,
        "recommended_power": 1350,
        "coin_reward": 800,
        "first_clear_gems": 100,
        "first_clear_shards": 4,
        "waves": [
            _wave([("oncall_warrior", 19), ("rogue_dba", 19), ("shadow_it_operator", 19)]),
            _wave([("build_engineer", 20), ("oncall_warrior", 20), ("midnight_pager", 20)]),
            _wave([("shadow_it_operator", 22), ("midnight_pager", 22)]),
        ],
    },
    {
        "code": "pager_storm",
        "name": "The Pager Storm",
        "order": 8,
        "energy_cost": 10,
        "recommended_power": 1600,
        "coin_reward": 1000,
        "first_clear_gems": 120,
        "first_clear_shards": 4,
        "waves": [
            _wave([("midnight_pager", 22), ("oncall_warrior", 22), ("the_post_mortem", 22)]),
            _wave([("chaos_monkey", 24), ("shadow_it_operator", 24), ("rogue_dba", 24)]),
            _wave([("chaos_monkey", 26), ("the_post_mortem", 25)]),
        ],
    },
    {
        "code": "hostile_acquisition",
        "name": "Hostile Acquisition",
        "order": 9,
        "energy_cost": 12,
        "recommended_power": 1900,
        "coin_reward": 1300,
        "first_clear_gems": 150,
        "first_clear_shards": 5,
        "waves": [
            _wave([("the_consultant", 26), ("vp_of_vibes", 26), ("compliance_officer", 26)]),
            _wave([("the_founder", 27), ("the_consultant", 28), ("security_auditor", 27)]),
            _wave([("the_board_member", 28), ("the_founder", 28)]),
        ],
    },
    {
        "code": "the_singularity",
        "name": "The Singularity",
        "order": 10,
        "energy_cost": 15,
        "recommended_power": 2400,
        "coin_reward": 1700,
        "first_clear_gems": 200,
        "first_clear_shards": 6,
        "waves": [
            _wave([("chaos_monkey", 28), ("shadow_it_operator", 28), ("rogue_dba", 28)]),
            _wave([("the_consultant", 29), ("retired_mainframe_guru", 29), ("the_board_member", 29)]),
            _wave([("the_founder", 30), ("chaos_monkey", 30), ("the_board_member", 30)]),
        ],
    },
]


def seed() -> None:
    _ensure_schema()
    with SessionLocal() as db:
        existing_hero_codes = set(db.scalars(select(HeroTemplate.code)).all())
        added_h = 0
        for h in HERO_SEEDS:
            if h["code"] in existing_hero_codes:
                continue
            db.add(HeroTemplate(
                code=h["code"], name=h["name"], rarity=h["rarity"],
                faction=h["faction"], role=h["role"],
                base_hp=h["base_hp"], base_atk=h["base_atk"],
                base_def=h["base_def"], base_spd=h["base_spd"],
                basic_mult=h["basic_mult"],
                special_json=json.dumps(h["special"]),
                special_cooldown=h["special_cooldown"],
            ))
            added_h += 1

        existing_stage_codes = set(db.scalars(select(Stage.code)).all())
        added_s = 0
        for s in STAGE_SEEDS:
            if s["code"] in existing_stage_codes:
                continue
            db.add(Stage(
                code=s["code"], name=s["name"], order=s["order"],
                energy_cost=s["energy_cost"],
                recommended_power=s["recommended_power"],
                waves_json=json.dumps(s["waves"]),
                coin_reward=s["coin_reward"],
                first_clear_gems=s["first_clear_gems"],
                first_clear_shards=s["first_clear_shards"],
            ))
            added_s += 1

        # Welcome LiveOps event: 7-day DOUBLE_REWARDS window starting now.
        added_l = 0
        has_event = db.scalar(
            select(LiveOpsEvent).where(LiveOpsEvent.name == "Launch Week 2x")
        )
        if has_event is None:
            now = utcnow()
            db.add(LiveOpsEvent(
                kind=LiveOpsKind.DOUBLE_REWARDS,
                name="Launch Week 2x",
                starts_at=now,
                ends_at=now + timedelta(days=7),
                payload_json=json.dumps({"multiplier": 2.0}),
            ))
            added_l = 1

        db.commit()
        print(f"seeded heroes+={added_h} stages+={added_s} liveops+={added_l}")


if __name__ == "__main__":
    seed()
