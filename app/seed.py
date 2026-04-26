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
    ShopProduct,
    ShopProductKind,
    Stage,
    StageDifficulty,
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
    # --- Expansion 2: more roster variety + 3 boss-scaled templates for raids ---
    {
        "code": "frontline_l1_tech",
        "name": "Frontline L1 Tech",
        "rarity": Rarity.COMMON, "faction": Faction.HELPDESK, "role": Role.DEF,
        "base_hp": 1200, "base_atk": 60, "base_def": 100, "base_spd": 80,
        "basic_mult": 0.9, "special": None, "special_cooldown": 0,
    },
    {
        "code": "office_coffee_hoarder",
        "name": "Office Coffee Hoarder",
        "rarity": Rarity.COMMON, "faction": Faction.ROGUE_IT, "role": Role.SUP,
        "base_hp": 950, "base_atk": 65, "base_def": 70, "base_spd": 110,
        "basic_mult": 0.8,
        "special": {
            "name": "Fresh Brew", "type": "BUFF",
            "target": "ally_lowest_hp",
            "effect": {"kind": "ATK_UP", "turns": 2, "value": 0.15},
        },
        "special_cooldown": 3,
    },
    {
        "code": "database_archaeologist",
        "name": "Database Archaeologist",
        "rarity": Rarity.UNCOMMON, "faction": Faction.LEGACY, "role": Role.SUP,
        "base_hp": 1100, "base_atk": 80, "base_def": 95, "base_spd": 90,
        "basic_mult": 0.9,
        "special": {
            "name": "Forgotten Query", "type": "DEBUFF",
            "target": "enemy_lowest_hp",
            "effect": {"kind": "POISON", "turns": 3, "value": 0.1},
        },
        "special_cooldown": 3,
    },
    {
        "code": "agile_coach",
        "name": "Agile Coach",
        "rarity": Rarity.UNCOMMON, "faction": Faction.EXECUTIVE, "role": Role.SUP,
        "base_hp": 1100, "base_atk": 80, "base_def": 85, "base_spd": 110,
        "basic_mult": 0.8,
        "special": {
            "name": "Sprint Retro", "type": "AOE_BUFF",
            "effect": {"kind": "ATK_UP", "turns": 2, "value": 0.18},
        },
        "special_cooldown": 4,
    },
    {
        "code": "cert_collector",
        "name": "Cert Collector",
        "rarity": Rarity.RARE, "faction": Faction.HELPDESK, "role": Role.DEF,
        "base_hp": 1700, "base_atk": 90, "base_def": 150, "base_spd": 90,
        "basic_mult": 1.0,
        "special": {
            "name": "Hyper-V / vSphere / K8s", "type": "SHIELD",
            "target": "self",
            "self_effect": {"kind": "ATK_UP", "turns": 2, "value": 0.2},
        },
        "special_cooldown": 4,
    },
    {
        "code": "blue_team_lead",
        "name": "Blue Team Lead",
        "rarity": Rarity.RARE, "faction": Faction.DEVOPS, "role": Role.DEF,
        "base_hp": 1650, "base_atk": 95, "base_def": 145, "base_spd": 100,
        "basic_mult": 1.0,
        "special": {
            "name": "Incident Commander", "type": "AOE_BUFF",
            "effect": {"kind": "ATK_UP", "turns": 2, "value": 0.25},
        },
        "special_cooldown": 4,
    },
    {
        "code": "tape_library_ghost",
        "name": "Tape Library Ghost",
        "rarity": Rarity.EPIC, "faction": Faction.LEGACY, "role": Role.DEF,
        "base_hp": 2100, "base_atk": 110, "base_def": 170, "base_spd": 85,
        "basic_mult": 1.0,
        "special": {
            "name": "Backup From 2003", "type": "REVIVE",
            "frac": 0.5,
        },
        "special_cooldown": 6,
    },
    # --- Boss-tier raid templates: hp-heavy, long cooldown signature specials.
    # Each uses the BOSS_PHASE special type — multi-effect AOE strike + boss
    # self-buff in a single cast. Mechanically distinct from any hero special.
    {
        "code": "raidboss_legacy_colossus",
        "name": "Legacy Colossus",
        "rarity": Rarity.LEGENDARY, "faction": Faction.LEGACY, "role": Role.DEF,
        "base_hp": 3400, "base_atk": 180, "base_def": 220, "base_spd": 80,
        "basic_mult": 1.1,
        # Bureaucratic Inertia: AOE chunk + DEF_DOWN + HEAL_BLOCK (no escape via
        # heal). Boss layers REFLECT on itself each phase, so the longer the
        # fight goes, the more dangerous it is to focus the boss.
        "special": {
            "name": "Bureaucratic Inertia", "type": "BOSS_PHASE",
            "mult": 1.5,
            "effects": [
                {"kind": "DEF_DOWN", "turns": 3, "value": 0.35},
                {"kind": "HEAL_BLOCK", "turns": 2, "value": 1.0},
            ],
            "self_effects": [
                {"kind": "REFLECT", "turns": 4, "value": 0.30},
            ],
        },
        "special_cooldown": 5,
    },
    {
        "code": "raidboss_c_suite_hydra",
        "name": "C-Suite Hydra",
        "rarity": Rarity.LEGENDARY, "faction": Faction.EXECUTIVE, "role": Role.ATK,
        "base_hp": 3100, "base_atk": 260, "base_def": 140, "base_spd": 130,
        "basic_mult": 1.2,
        # Mandatory Re-Org: AOE damage + freezes every survivor for one turn.
        # Forces the team to break the freeze (any damage clears it) on the
        # heroes you most want acting next — priority puzzle every cast.
        # Self-buffs ATK_UP for the inevitable next phase.
        "special": {
            "name": "Mandatory Re-Org", "type": "BOSS_PHASE",
            "mult": 1.4,
            "effects": [
                {"kind": "FREEZE", "turns": 1, "value": 1.0},
            ],
            "self_effects": [
                {"kind": "ATK_UP", "turns": 3, "value": 0.30},
            ],
        },
        "special_cooldown": 4,
    },
    {
        "code": "raidboss_chaos_dragon",
        "name": "Chaos Dragon",
        "rarity": Rarity.LEGENDARY, "faction": Faction.DEVOPS, "role": Role.ATK,
        "base_hp": 3600, "base_atk": 240, "base_def": 160, "base_spd": 150,
        "basic_mult": 1.15,
        # Cascading Outage: AOE chunk + stacking BURN on the whole team. BURN
        # ticks every actor's turn so a long fight just bleeds the team out.
        # Boss self-buffs ATK_UP — escalation pressure.
        "special": {
            "name": "Cascading Outage", "type": "BOSS_PHASE",
            "mult": 1.5,
            "effects": [
                {"kind": "BURN", "turns": 3, "value": 0.10},
            ],
            "self_effects": [
                {"kind": "ATK_UP", "turns": 3, "value": 0.20},
            ],
        },
        "special_cooldown": 5,
    },
    # --- MYTH tier: event-only, never in standard gacha pool. Pilot hero to
    # exercise the new rarity tier end-to-end. ---
    {
        "code": "tbfam",  # "The Brother From Another Mother"
        "name": "TBFAM",
        "rarity": Rarity.MYTH, "faction": Faction.EXECUTIVE, "role": Role.ATK,
        "base_hp": 2200, "base_atk": 310, "base_def": 150, "base_spd": 160,
        "basic_mult": 1.2,
        "special": {
            "name": "Everything on the Desk", "type": "AOE_DAMAGE",
            "mult": 2.5, "hits": 4,  # four monitors / keyboards / paperweights
            "effect": {"kind": "STUN", "turns": 1, "value": 1.0},
            "self_effect": {"kind": "ATK_UP", "turns": 3, "value": 0.5},  # instant rage
        },
        "special_cooldown": 4,
    },
    {
        # MYTH support pair to TBFAM. Mother's Day 2026 event hero.
        # Card art is intentionally inverted — that's a stylistic choice for the
        # event, not an upload bug. See docs/hero_art_prompts.md.
        "code": "applecrumb",
        "name": "Applecrumb",
        "rarity": Rarity.MYTH, "faction": Faction.EXECUTIVE, "role": Role.SUP,
        # Tanky support stats — high HP/DEF, modest ATK, decent SPD so the heal
        # lands before allies fall.
        "base_hp": 2400, "base_atk": 180, "base_def": 200, "base_spd": 145,
        "basic_mult": 0.9,
        "special": {
            # Family Office Meeting: AOE heal for the team + ATK_UP buff for
            # each ally on the same cast. The defining "mom fixes everything"
            # support move — pairs naturally with TBFAM's burst rage comp.
            "name": "Family Office Meeting", "type": "AOE_HEAL",
            "frac": 0.35,
            "effect": {"kind": "ATK_UP", "turns": 3, "value": 0.25},
        },
        "special_cooldown": 5,
    },
]


# --- Stages ------------------------------------------------------------------


def _wave(enemies: list[tuple[str, int]]) -> dict:
    return {"enemies": [{"template_code": code, "level": level} for code, level in enemies]}


STAGE_SEEDS: list[dict] = [
    # --- Tutorial: order=0, single-wave trivial enemy, no real cost. Used by
    # the first-time-walkthrough UI to teach the combat loop before order=1.
    {
        "code": "tutorial_first_ticket",
        "name": "First Ticket",
        "order": 0,
        "energy_cost": 0,
        "recommended_power": 60,
        "coin_reward": 50,
        "first_clear_gems": 10,
        "first_clear_shards": 0,
        "waves": [
            _wave([("ticket_gremlin", 1)]),
        ],
    },
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
    # --- Expansion 2: endgame progression (orders 11-15) ---
    {
        "code": "tape_room_breach",
        "name": "Tape Room Breach",
        "order": 11,
        "energy_cost": 15,
        "recommended_power": 2800,
        "coin_reward": 2100,
        "first_clear_gems": 220,
        "first_clear_shards": 7,
        "waves": [
            _wave([("tape_library_ghost", 30), ("cert_collector", 30), ("database_archaeologist", 30)]),
            _wave([("tape_library_ghost", 32), ("retired_mainframe_guru", 31)]),
            _wave([("raidboss_legacy_colossus", 30), ("tape_library_ghost", 32)]),
        ],
    },
    {
        "code": "boardroom_coup",
        "name": "The Boardroom Coup",
        "order": 12,
        "energy_cost": 16,
        "recommended_power": 3100,
        "coin_reward": 2400,
        "first_clear_gems": 250,
        "first_clear_shards": 8,
        "waves": [
            _wave([("the_board_member", 30), ("agile_coach", 30), ("the_consultant", 30)]),
            _wave([("the_founder", 31), ("vp_of_vibes", 31), ("the_board_member", 31)]),
            _wave([("raidboss_c_suite_hydra", 30), ("the_founder", 31)]),
        ],
    },
    {
        "code": "prod_is_down",
        "name": "Prod Is Down",
        "order": 13,
        "energy_cost": 16,
        "recommended_power": 3400,
        "coin_reward": 2700,
        "first_clear_gems": 275,
        "first_clear_shards": 8,
        "waves": [
            _wave([("midnight_pager", 30), ("oncall_warrior", 30), ("the_post_mortem", 30)]),
            _wave([("chaos_monkey", 32), ("shadow_it_operator", 32), ("blue_team_lead", 32)]),
            _wave([("raidboss_chaos_dragon", 30), ("chaos_monkey", 32)]),
        ],
    },
    {
        "code": "the_unauthorized_tool",
        "name": "The Unauthorized Tool",
        "order": 14,
        "energy_cost": 17,
        "recommended_power": 3700,
        "coin_reward": 3000,
        "first_clear_gems": 300,
        "first_clear_shards": 9,
        "waves": [
            _wave([("shadow_it_operator", 32), ("rogue_dba", 32), ("root_access_janitor", 32)]),
            _wave([("forgotten_contractor", 33), ("shadow_it_operator", 33), ("chaos_monkey", 33)]),
            _wave([("raidboss_chaos_dragon", 32), ("raidboss_legacy_colossus", 32)]),
        ],
    },
    {
        "code": "the_all_hands",
        "name": "The All-Hands",
        "order": 15,
        "energy_cost": 18,
        "recommended_power": 4100,
        "coin_reward": 3400,
        "first_clear_gems": 350,
        "first_clear_shards": 10,
        "waves": [
            _wave([("the_board_member", 33), ("the_founder", 33), ("vp_of_vibes", 33)]),
            _wave([("raidboss_legacy_colossus", 33), ("raidboss_chaos_dragon", 33), ("raidboss_c_suite_hydra", 33)]),
            _wave([("the_founder", 35), ("raidboss_c_suite_hydra", 35), ("the_board_member", 35)]),
        ],
    },
]


# --- Shop catalog ------------------------------------------------------------
#
# Prices roughly mirror western mobile F2P tuning — the starter pack is a soft
# first-purchase conversion at $1.99, gem tiers step up to $49.99 "best value",
# access_cards (premium character-pack currency) priced at a deliberate premium.
# All are catalog entries; real Stripe integration is a later sprint.

SHOP_SEEDS: list[dict] = [
    # Starter pack — cheap $1.99 first-purchase converter.
    {
        "sku": "starter_pack", "title": "Starter Pack",
        "description": "New-player bundle: 500 gems, 100 shards, 5 access cards. One-time only.",
        "kind": ShopProductKind.STARTER_BUNDLE,
        "price_cents": 199, "sort_order": 10, "per_account_limit": 1,
        "contents": {"gems": 500, "shards": 100, "access_cards": 5},
    },
    # Jump-Ahead Bundle — richer starter for $4.99. Adds one RARE hero so
    # players who want to skip the early COMMON grind can, without paywalling
    # EPIC/LEGENDARY (those stay gacha-only to keep the PoE2-style tone).
    # 7-day availability window is enforced at the UI level (ui.partial_summon
    # checks starter_expires_at against Account.created_at). Backend just
    # honors per_account_limit=1.
    {
        "sku": "starter_jumpahead", "title": "Jump-Ahead Bundle",
        "description": "500 gems, 50 shards, 3 access cards, and one RARE helpdesk hero (Keymaster Gary). One-time only, first 7 days.",
        "kind": ShopProductKind.STARTER_BUNDLE,
        "price_cents": 499, "sort_order": 20, "per_account_limit": 1,
        "contents": {
            "gems": 500, "shards": 50, "access_cards": 3,
            "hero_template_code": "keymaster_gary",
        },
    },
    # Gem packs — standard premium-currency ladder.
    {
        "sku": "gems_small", "title": "Pocket Change",
        "description": "300 💎 gems.",
        "kind": ShopProductKind.GEM_PACK, "price_cents": 499, "sort_order": 100,
        "contents": {"gems": 300},
    },
    {
        "sku": "gems_medium", "title": "Slush Fund",
        "description": "1400 💎 gems. (+12% bonus)",
        "kind": ShopProductKind.GEM_PACK, "price_cents": 1999, "sort_order": 110,
        "contents": {"gems": 1400},
    },
    {
        "sku": "gems_large", "title": "Off-the-Books Budget",
        "description": "3800 💎 gems. (+26% bonus — best value)",
        "kind": ShopProductKind.GEM_PACK, "price_cents": 4999, "sort_order": 120,
        "contents": {"gems": 3800},
    },
    # Shard pack — lower tier, gameplay-adjacent currency.
    {
        "sku": "shards_pack", "title": "Summoning Cache",
        "description": "150 ✦ shards — enough for a 10-pull.",
        "kind": ShopProductKind.SHARD_PACK, "price_cents": 999, "sort_order": 200,
        "contents": {"shards": 150},
    },
    # Access cards — premium character-pack currency. Deliberately pricey.
    {
        "sku": "access_cards_pack", "title": "Keymaster's Bundle",
        "description": "15 🎫 access cards for featured character packs.",
        "kind": ShopProductKind.ACCESS_CARD_PACK, "price_cents": 999, "sort_order": 300,
        "contents": {"access_cards": 15},
    },
    # Weekly bundle — mixed-currency good-value offer. Timed window seeded separately.
    {
        "sku": "weekly_bundle", "title": "Weekly Ops Kit",
        "description": "700 💎 gems + 40 ✦ shards + 3 🎫 access cards. Resets weekly.",
        "kind": ShopProductKind.WEEKLY_BUNDLE, "price_cents": 999, "sort_order": 400,
        "per_account_limit": 0,  # intended to recur weekly in later sprints
        "contents": {"gems": 700, "shards": 40, "access_cards": 3},
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
            if s["code"] not in existing_stage_codes:
                db.add(Stage(
                    code=s["code"], name=s["name"], order=s["order"],
                    energy_cost=s["energy_cost"],
                    recommended_power=s["recommended_power"],
                    waves_json=json.dumps(s["waves"]),
                    coin_reward=s["coin_reward"],
                    first_clear_gems=s["first_clear_gems"],
                    first_clear_shards=s["first_clear_shards"],
                    difficulty_tier=StageDifficulty.NORMAL,
                ))
                added_s += 1

            # --- HARD tier: same waves, enemies +10 levels, 1.5x rewards, gated on NORMAL clear.
            hard_code = f"H-{s['code']}"
            if hard_code not in existing_stage_codes:
                scaled_waves = []
                for w in s["waves"]:
                    scaled_waves.append({
                        "enemies": [
                            {"template_code": e["template_code"], "level": int(e.get("level", 1)) + 10}
                            for e in w.get("enemies", [])
                        ]
                    })
                db.add(Stage(
                    code=hard_code,
                    name=f"{s['name']} (Hard)",
                    order=s["order"] + 100,   # keeps NORMAL sorted first by `order`
                    energy_cost=s["energy_cost"] + 1,
                    recommended_power=s["recommended_power"] * 2,
                    waves_json=json.dumps(scaled_waves),
                    coin_reward=int(s["coin_reward"] * 1.5),
                    first_clear_gems=s["first_clear_gems"] * 2,
                    first_clear_shards=s["first_clear_shards"] * 2,
                    difficulty_tier=StageDifficulty.HARD,
                    requires_code=s["code"],
                ))
                added_s += 1

        # Welcome LiveOps events: 7-day DOUBLE_REWARDS window + 3-day
        # BONUS_GEAR_DROPS overlapping. Both seed idempotently by name.
        added_l = 0
        now = utcnow()
        _events_to_seed = [
            ("Launch Week 2x", LiveOpsKind.DOUBLE_REWARDS, 7, {"multiplier": 2.0}),
            ("Gear Hunt Weekend", LiveOpsKind.BONUS_GEAR_DROPS, 3, {"chance_add": 0.25}),
        ]
        for ev_name, kind, days, payload in _events_to_seed:
            if db.scalar(select(LiveOpsEvent).where(LiveOpsEvent.name == ev_name)) is None:
                db.add(LiveOpsEvent(
                    kind=kind,
                    name=ev_name,
                    starts_at=now,
                    ends_at=now + timedelta(days=days),
                    payload_json=json.dumps(payload),
                ))
                added_l += 1

        # Shop catalog.
        existing_skus = set(db.scalars(select(ShopProduct.sku)).all())
        added_p = 0
        for p in SHOP_SEEDS:
            if p["sku"] in existing_skus:
                continue
            db.add(ShopProduct(
                sku=p["sku"], title=p["title"], description=p.get("description", ""),
                kind=p["kind"], price_cents=p["price_cents"],
                currency_code=p.get("currency_code", "USD"),
                contents_json=json.dumps(p["contents"]),
                sort_order=p.get("sort_order", 100),
                per_account_limit=p.get("per_account_limit", 0),
            ))
            added_p += 1

        db.commit()
        print(f"seeded heroes+={added_h} stages+={added_s} liveops+={added_l} products+={added_p}")


if __name__ == "__main__":
    seed()
