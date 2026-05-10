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
    GuildAchievement,
    HeroTemplate,
    LiveOpsEvent,
    LiveOpsKind,
    OfferBundle,
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
    # --- Phase 3.5 alignment-exclusive heroes -----------------------------------
    # These are NOT in the standard summon pool. They are granted automatically
    # on completing the alignment-specific epic chapter. Seeded here so combat
    # stats and specials are queryable; the summon router ignores RESISTANCE /
    # CORP_GREED factions the same way it ignores MYTH.
    {
        "code": "the_whistleblower",
        "name": "The Whistleblower",
        "rarity": Rarity.EPIC, "faction": Faction.RESISTANCE, "role": Role.SUP,
        # Tanky support — high HP keeps them alive to enable the team.
        "base_hp": 2100, "base_atk": 140, "base_def": 165, "base_spd": 120,
        "basic_mult": 0.85,
        "special": {
            # Leak The Memo: AOE buff to all allies + AOE DEF_DOWN on all enemies.
            # Turns the whole fight tempo in one cast — burst windows open immediately.
            "name": "Leak The Memo", "type": "AOE_BUFF",
            "effect": {"kind": "ATK_UP", "turns": 3, "value": 0.35},
            "debuff": {"kind": "DEF_DOWN", "turns": 2, "value": 0.30},
        },
        "special_cooldown": 5,
    },
    {
        "code": "the_successor",
        "name": "The Successor",
        "rarity": Rarity.EPIC, "faction": Faction.CORP_GREED, "role": Role.ATK,
        # Glass-cannon burst — trades HP for the highest ATK in the EPIC tier.
        "base_hp": 1850, "base_atk": 285, "base_def": 120, "base_spd": 145,
        "basic_mult": 1.1,
        "special": {
            # Hostile Takeover: heavy AOE strike + self ATK_UP + enemy HEAL_BLOCK.
            # Punishes sustain comps while ramping own damage ceiling.
            "name": "Hostile Takeover", "type": "AOE_DAMAGE",
            "mult": 2.0,
            "effect": {"kind": "HEAL_BLOCK", "turns": 2, "value": 1.0},
            "self_effect": {"kind": "ATK_UP", "turns": 3, "value": 0.45},
        },
        "special_cooldown": 5,
    },
    {
        # Summer Slowdown 2026 event hero (July 4th / Canada Day week).
        # The one poor soul whose pager went off during the BBQ. MYTH DEF —
        # tanky frontline who puts the whole team into Incident Response mode.
        "code": "on_call_martyr",
        "name": "The On-Call Martyr",
        "rarity": Rarity.MYTH, "faction": Faction.HELPDESK, "role": Role.DEF,
        "base_hp": 2800, "base_atk": 140, "base_def": 260, "base_spd": 120,
        "basic_mult": 0.85,
        "special": {
            # Emergency Change Window: slaps REFLECT on every ally for 2 turns.
            # Attackers who pile on during the holiday weekend pay for it.
            "name": "Emergency Change Window", "type": "AOE_BUFF",
            "effect": {"kind": "REFLECT", "turns": 2, "value": 0.30},
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
    # --- Phase 3.5: RESISTANCE alignment chapter — "The Infiltration" (orders 50-54)
    # Only accessible after choosing RESISTANCE at level 50. Enemies are Corp
    # enforcers (EXECUTIVE / ROGUE_IT) who protect the performance metrics server.
    {
        "code": "resistance_breach",
        "name": "Breach — Through the Lobby",
        "order": 50,
        "energy_cost": 18,
        "recommended_power": 4200,
        "coin_reward": 3500,
        "first_clear_gems": 400,
        "first_clear_shards": 12,
        "waves": [
            _wave([("compliance_officer", 36), ("security_auditor", 36), ("agile_coach", 36)]),
            _wave([("the_consultant", 37), ("vp_of_vibes", 37), ("compliance_officer", 37)]),
        ],
    },
    {
        "code": "resistance_server_room",
        "name": "The Metrics Server",
        "order": 51,
        "energy_cost": 19,
        "recommended_power": 4600,
        "coin_reward": 3900,
        "first_clear_gems": 450,
        "first_clear_shards": 13,
        "waves": [
            _wave([("the_board_member", 37), ("shadow_it_operator", 37), ("midnight_pager", 37)]),
            _wave([("raidboss_legacy_colossus", 36), ("the_board_member", 38)]),
        ],
    },
    {
        "code": "resistance_boardroom",
        "name": "Storm the Boardroom",
        "order": 52,
        "energy_cost": 20,
        "recommended_power": 5000,
        "coin_reward": 4300,
        "first_clear_gems": 500,
        "first_clear_shards": 14,
        "waves": [
            _wave([("the_founder", 38), ("agile_coach", 38), ("the_consultant", 38)]),
            _wave([("the_founder", 40), ("raidboss_c_suite_hydra", 37), ("vp_of_vibes", 39)]),
        ],
    },
    {
        "code": "resistance_coup",
        "name": "Topple the Corp",
        "order": 53,
        "energy_cost": 20,
        "recommended_power": 5400,
        "coin_reward": 4800,
        "first_clear_gems": 550,
        "first_clear_shards": 15,
        "waves": [
            _wave([("raidboss_c_suite_hydra", 38), ("the_board_member", 40), ("the_founder", 40)]),
            _wave([("raidboss_legacy_colossus", 38), ("raidboss_c_suite_hydra", 38)]),
        ],
    },
    {
        "code": "resistance_aftermath",
        "name": "The Whistleblower Speaks",
        "order": 54,
        "energy_cost": 22,
        "recommended_power": 5800,
        "coin_reward": 5500,
        "first_clear_gems": 600,
        "first_clear_shards": 20,
        "waves": [
            _wave([("the_founder", 42), ("raidboss_legacy_colossus", 40), ("raidboss_c_suite_hydra", 40)]),
            _wave([("the_founder", 45), ("raidboss_c_suite_hydra", 42), ("raidboss_chaos_dragon", 40)]),
        ],
    },
    # --- Phase 3.5: CORP_GREED alignment chapter — "The Ascension" (orders 60-64)
    # Only accessible after choosing CORP_GREED at level 50. Enemies are the
    # existing Resistance and rogue operators who stand between the player and the board.
    {
        "code": "corpgreed_first_move",
        "name": "The Power Play",
        "order": 60,
        "energy_cost": 18,
        "recommended_power": 4200,
        "coin_reward": 3500,
        "first_clear_gems": 400,
        "first_clear_shards": 12,
        "waves": [
            _wave([("rogue_dba", 36), ("shadow_it_operator", 36), ("oncall_warrior", 36)]),
            _wave([("build_engineer", 37), ("helpdesk_veteran", 37), ("rogue_dba", 37)]),
        ],
    },
    {
        "code": "corpgreed_acquisition",
        "name": "Hostile Acquisition",
        "order": 61,
        "energy_cost": 19,
        "recommended_power": 4600,
        "coin_reward": 3900,
        "first_clear_gems": 450,
        "first_clear_shards": 13,
        "waves": [
            _wave([("retired_mainframe_guru", 37), ("blue_team_lead", 37), ("build_engineer", 37)]),
            _wave([("raidboss_chaos_dragon", 36), ("oncall_warrior", 38)]),
        ],
    },
    {
        "code": "corpgreed_boardroom",
        "name": "A Seat at the Table",
        "order": 62,
        "energy_cost": 20,
        "recommended_power": 5000,
        "coin_reward": 4300,
        "first_clear_gems": 500,
        "first_clear_shards": 14,
        "waves": [
            _wave([("helpdesk_veteran", 38), ("oncall_warrior", 38), ("build_engineer", 38)]),
            _wave([("raidboss_chaos_dragon", 37), ("rogue_dba", 40), ("build_engineer", 39)]),
        ],
    },
    {
        "code": "corpgreed_saas",
        "name": "Monetize Everything",
        "order": 63,
        "energy_cost": 20,
        "recommended_power": 5400,
        "coin_reward": 4800,
        "first_clear_gems": 550,
        "first_clear_shards": 15,
        "waves": [
            _wave([("raidboss_chaos_dragon", 38), ("blue_team_lead", 40), ("rogue_dba", 40)]),
            _wave([("raidboss_legacy_colossus", 38), ("raidboss_chaos_dragon", 38)]),
        ],
    },
    {
        "code": "corpgreed_apotheosis",
        "name": "Become the Corp",
        "order": 64,
        "energy_cost": 22,
        "recommended_power": 5800,
        "coin_reward": 5500,
        "first_clear_gems": 600,
        "first_clear_shards": 20,
        "waves": [
            _wave([("helpdesk_veteran", 42), ("raidboss_chaos_dragon", 40), ("raidboss_legacy_colossus", 40)]),
            _wave([("raidboss_chaos_dragon", 42), ("raidboss_legacy_colossus", 42), ("raidboss_c_suite_hydra", 40)]),
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
    # Coin packs — soft premium currency for the in-game economy.
    {
        "sku": "coin_sack_daily", "title": "Coin Sack",
        "description": "5,000 coins. Free once per day.",
        "kind": ShopProductKind.COIN_PACK, "price_cents": 0, "sort_order": 50,
        "per_account_limit": 1,
        "contents": {"coins": 5000},
    },
    {
        "sku": "coin_chest", "title": "Coin Chest",
        "description": "25,000 coins. Classic IT salary move.",
        "kind": ShopProductKind.COIN_PACK, "price_cents": 99, "sort_order": 51,
        "per_account_limit": 0,
        "contents": {"coins": 25000},
    },
    {
        "sku": "coin_vault", "title": "Coin Vault",
        "description": "100,000 coins. Senior dev territory.",
        "kind": ShopProductKind.COIN_PACK, "price_cents": 199, "sort_order": 52,
        "per_account_limit": 0,
        "contents": {"coins": 100000},
    },
    {
        "sku": "devs_stash", "title": "Dev's Stash",
        "description": "500,000 coins. The Rootlord's personal reserve.",
        "kind": ShopProductKind.COIN_PACK, "price_cents": 499, "sort_order": 53,
        "per_account_limit": 0,
        "contents": {"coins": 500000},
    },
    # Weekly bundle — mixed-currency good-value offer. Timed window seeded separately.
    {
        "sku": "weekly_bundle", "title": "Weekly Ops Kit",
        "description": "700 💎 gems + 40 ✦ shards + 3 🎫 access cards. Resets weekly.",
        "kind": ShopProductKind.WEEKLY_BUNDLE, "price_cents": 999, "sort_order": 400,
        "per_account_limit": 0,  # intended to recur weekly in later sprints
        "contents": {"gems": 700, "shards": 40, "access_cards": 3},
    },
    # --- PoE2-style QoL catalog (Phase 2.4) ---------------------------------
    # Tone lock: cosmetic / QoL only, never raw power. F2P viability is
    # non-negotiable — every gameplay path stays reachable without spending.
    # Catalog codes must match KNOWN_QOL_UNLOCKS / KNOWN_COSMETIC_FRAMES in
    # app/store.py or apply_grant raises.
    {
        "sku": "qol_auto_battle", "title": "QoL: Auto-Battle",
        "description": "Skip the watch — collapses /battles into one POST. One-time unlock. Pure QoL, never sold for power.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 499, "sort_order": 500,
        "per_account_limit": 1,
        "contents": {"qol_unlocks": ["auto_battle"]},
    },
    {
        "sku": "qol_extra_presets", "title": "QoL: Extra Preset Slots",
        "description": "Bumps the team-preset cap from 5 to 10. One-time unlock.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 299, "sort_order": 510,
        "per_account_limit": 1,
        "contents": {"qol_unlocks": ["extra_team_presets"]},
    },
    {
        "sku": "qol_quick_summon", "title": "QoL: Quick Summon",
        "description": "Skip the per-pull animation on x10. Cosmetic. One-time unlock.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 199, "sort_order": 520,
        "per_account_limit": 1,
        "contents": {"qol_unlocks": ["quick_summon"]},
    },
    {
        "sku": "qol_roster_sort", "title": "QoL: Advanced Roster Sort",
        "description": "Roster filter / sort options beyond the default rarity+power view.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 199, "sort_order": 530,
        "per_account_limit": 1,
        "contents": {"qol_unlocks": ["roster_sort_advanced"]},
    },
    # Inventory expansions — additive caps. Stackable, no per-account limit.
    {
        "sku": "slots_hero_pack", "title": "Roster Expansion (+25 hero slots)",
        "description": "Bumps hero_slot_cap by 25. Stackable.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 299, "sort_order": 600,
        "per_account_limit": 0,
        "contents": {"extra_hero_slots": 25},
    },
    {
        "sku": "slots_gear_pack", "title": "Stash Expansion (+100 gear slots)",
        "description": "Bumps gear_slot_cap by 100. Stackable.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 299, "sort_order": 610,
        "per_account_limit": 0,
        "contents": {"extra_gear_slots": 100},
    },
    # Cosmetic frames — pure visual flair, no power. Single-frame SKUs +
    # one bundle for the recurring-spend path.
    {
        "sku": "cosmetic_frame_neon", "title": "Cosmetic: Neon Cubicle Frame",
        "description": "Hero card frame in neon-cubicle palette. Cosmetic.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 199, "sort_order": 700,
        "per_account_limit": 1,
        "contents": {"cosmetic_frames": ["frame_neon_cubicle"]},
    },
    {
        "sku": "cosmetic_frame_terminal", "title": "Cosmetic: Terminal Green Frame",
        "description": "Hero card frame in monochrome green. Cosmetic.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 199, "sort_order": 710,
        "per_account_limit": 1,
        "contents": {"cosmetic_frames": ["frame_terminal_green"]},
    },
    {
        "sku": "cosmetic_frame_bundle", "title": "Cosmetic: Frame Bundle",
        "description": "All four cosmetic frames at once. Cosmetic only.",
        "kind": ShopProductKind.SEASONAL_BUNDLE, "price_cents": 599, "sort_order": 750,
        "per_account_limit": 1,
        "contents": {"cosmetic_frames": [
            "frame_neon_cubicle", "frame_terminal_green",
            "frame_legacy_brass", "frame_corp_platinum",
        ]},
    },
]


# --- Offer bundles -----------------------------------------------------------
#
# Premium time-limited bundles with direct USD pricing. Distinct from the
# ShopProduct catalog — no Stripe price_id needed for mock-payment paths.
# Idempotent: added once by code, never overwritten. Add new bundles here to
# surface them via GET /shop/bundles.

OFFER_BUNDLE_SEEDS: list[dict] = [
    {
        "code": "starter_pack",
        "name": "Starter Pack",
        "description": "Jump-start your roster: 200 gems, 30 shards. One-time only.",
        "price_usd": 4.99,
        "gems": 200,
        "shards": 30,
        "one_per_account": True,
    },
    {
        "code": "gem_pack_small",
        "name": "Small Gem Pack",
        "description": "100 gems. Stackable — buy as many times as you like.",
        "price_usd": 1.99,
        "gems": 100,
        "one_per_account": False,
    },
    {
        "code": "shard_surge",
        "name": "Shard Surge",
        "description": "100 shards for a big summon session. One-time only.",
        "price_usd": 2.99,
        "shards": 100,
        "one_per_account": True,
    },
    {
        "code": "vip_bundle",
        "name": "VIP Bundle",
        "description": "Best value: 500 gems, 50 shards, 10 access cards. One-time only.",
        "price_usd": 9.99,
        "gems": 500,
        "shards": 50,
        "access_cards": 10,
        "one_per_account": True,
    },
]


GUILD_ACHIEVEMENT_SEEDS: list[dict] = [
    {
        "code": "FIRST_MEMBER",
        "name": "First Recruit",
        "description": "A guild that grows together, stays together.",
        "category": "membership",
        "metric": "members_joined",
        "target_value": 2,
        "reward_gems": 50,
        "reward_coins": 500,
    },
    {
        "code": "GUILD_OF_5",
        "name": "Five Strong",
        "description": "Reach 5 total members.",
        "category": "membership",
        "metric": "members_joined",
        "target_value": 5,
        "reward_gems": 100,
        "reward_coins": 1000,
    },
    {
        "code": "GUILD_OF_10",
        "name": "Double Digits",
        "description": "Reach 10 total members.",
        "category": "membership",
        "metric": "members_joined",
        "target_value": 10,
        "reward_gems": 200,
        "reward_coins": 2000,
    },
    {
        "code": "FIRST_RAID",
        "name": "First Blood",
        "description": "Complete your first guild raid.",
        "category": "raids",
        "metric": "raids_completed",
        "target_value": 1,
        "reward_gems": 100,
        "reward_coins": 1000,
    },
    {
        "code": "RAID_VETERANS",
        "name": "Raid Veterans",
        "description": "Complete 10 guild raids.",
        "category": "raids",
        "metric": "raids_completed",
        "target_value": 10,
        "reward_gems": 300,
        "reward_coins": 3000,
    },
    {
        "code": "RAID_ELITE",
        "name": "Raid Elite",
        "description": "Complete 50 guild raids.",
        "category": "raids",
        "metric": "raids_completed",
        "target_value": 50,
        "reward_gems": 500,
        "reward_coins": 5000,
    },
    {
        "code": "FIRST_VICTORY",
        "name": "First Victory",
        "description": "Win your first battle as a guild.",
        "category": "battles",
        "metric": "battles_won",
        "target_value": 1,
        "reward_gems": 50,
        "reward_coins": 500,
    },
    {
        "code": "CENTURY",
        "name": "Centurions",
        "description": "Win 100 battles as a guild.",
        "category": "battles",
        "metric": "battles_won",
        "target_value": 100,
        "reward_gems": 400,
        "reward_coins": 4000,
    },
    {
        "code": "GUILD_CHAT_ACTIVE",
        "name": "Active Community",
        "description": "Send 100 messages in guild chat.",
        "category": "social",
        "metric": "messages_sent",
        "target_value": 100,
        "reward_gems": 150,
        "reward_coins": 1500,
    },
    {
        "code": "DAMAGE_DEALERS",
        "name": "Damage Dealers",
        "description": "Deal 1,000,000 total raid damage as a guild.",
        "category": "raids",
        "metric": "total_raid_damage",
        "target_value": 1_000_000,
        "reward_gems": 500,
        "reward_coins": 5000,
    },
]


def seed_guild_achievements(db) -> int:
    """Idempotent upsert of guild achievement definitions. Returns count added."""
    existing_codes = set(db.scalars(select(GuildAchievement.code)).all())
    added = 0
    for a in GUILD_ACHIEVEMENT_SEEDS:
        if a["code"] in existing_codes:
            continue
        db.add(GuildAchievement(
            code=a["code"],
            name=a["name"],
            description=a["description"],
            category=a["category"],
            metric=a["metric"],
            target_value=a["target_value"],
            reward_gems=a.get("reward_gems", 0),
            reward_coins=a.get("reward_coins", 0),
        ))
        added += 1
    return added


def seed_offer_bundles(db) -> int:
    """Idempotent upsert of offer bundles. Returns count added."""
    existing_codes = set(db.scalars(select(OfferBundle.code)).all())
    added = 0
    for b in OFFER_BUNDLE_SEEDS:
        if b["code"] in existing_codes:
            continue
        db.add(OfferBundle(
            code=b["code"],
            name=b["name"],
            description=b.get("description", ""),
            price_usd=b["price_usd"],
            gems=b.get("gems", 0),
            shards=b.get("shards", 0),
            coins=b.get("coins", 0),
            access_cards=b.get("access_cards", 0),
            hero_template_code=b.get("hero_template_code"),
            one_per_account=b.get("one_per_account", True),
            active=b.get("active", True),
        ))
        added += 1
    return added


def _piece_set(items: list[tuple[str, str, str]], *, completion_idx: int) -> list[dict]:
    """Build a list of piece dicts. items = [(code, name, icon), ...]."""
    out = []
    for i, (code, name, icon) in enumerate(items):
        out.append({
            "code": code, "name": name, "icon": icon,
            "flavor": "",
            "is_completion_piece": (i == completion_idx),
        })
    return out


def seed_collections(db: Session) -> int:
    """Upsert the 12 v1 collections. Idempotent."""
    from app.models import Collection

    DEFS = [
        # ── 1-20 bracket ──────────────────────────────────────────────────
        {
            "code": "cubicle_detritus",
            "name": "Cubicle Detritus",
            "theme": "The pile under the keyboard.",
            "rarity": "UNCOMMON", "level_bracket": "1-20", "sort_order": 1,
            "pieces": _piece_set([
                ("paperclip_red",   "Red Paperclip",   "📎"),
                ("paperclip_silver","Silver Paperclip","📎"),
                ("postit_yellow",   "Yellow Post-it",  "📒"),
                ("postit_pink",     "Pink Post-it",    "📒"),
                ("rubber_band",     "Rubber Band",     "⭕"),
                ("staple_box",      "Stapler Refill",  "📎"),
                ("pen_chewed",      "Chewed Pen",      "🖊️"),
                ("desk_dust_bunny", "Desk Dust Bunny", "💨"),
            ], completion_idx=7),
            "reward": {"kind": "frame", "frame_code": "cubicle_archaeologist"},
        },
        {
            "code": "onboarding_kit",
            "name": "Onboarding Kit",
            "theme": "Day-one swag that never quite fits.",
            "rarity": "RARE", "level_bracket": "1-20", "sort_order": 2,
            "pieces": _piece_set([
                ("badge_laminated", "Laminated Badge",  "🪪"),
                ("lanyard_logo",    "Logo Lanyard",     "🎗️"),
                ("welcome_mug",     "Welcome Mug",      "☕"),
                ("stress_ball",     "Stress Ball",      "🎾"),
                ("cable_bagged",    "Bagged USB Cable", "🔌"),
                ("notebook_blank",  "Blank Notebook",   "📔"),
                ("benefits_pdf",    "Benefits PDF (printed)", "📄"),
                ("welcome_keys",    "Welcome Keychain", "🔑"),
            ], completion_idx=7),
            "reward": {"kind": "currency", "coins": 500, "gems": 50, "shards": 10},
        },
        {
            "code": "helpdesk_starter",
            "name": "Help Desk Starter Pack",
            "theme": "Survival kit for the first three weeks.",
            "rarity": "EPIC", "level_bracket": "1-20", "sort_order": 3,
            "pieces": _piece_set([
                ("spare_kb",       "Spare Keyboard",      "⌨️"),
                ("password_sticky","Password Sticky-note","🔓"),
                ("energy_drink",   "Energy Drink Can",    "🥤"),
                ("ticket_dump",    "Ticket Queue Dump",   "🎫"),
                ("hold_music",     "On-Hold Music CD",    "💿"),
                ("escalation_doc", "Escalation Path PDF", "📋"),
                ("mouse_dirty",    "Crumby Mouse",        "🖱️"),
                ("aspirin_bottle", "Aspirin Bottle",      "💊"),
                ("kvm_switch",     "Old KVM Switch",      "🔀"),
                ("pager_dead",     "Dead Pager",          "📟"),
            ], completion_idx=9),
            "reward": {"kind": "hero_shards", "amount": 30, "rarity": "EPIC"},
        },
        {
            "code": "y2k_relics",
            "name": "Y2K Survival Relics",
            "theme": "What we hoarded under our desks in 1999.",
            "rarity": "LEGENDARY", "level_bracket": "1-20", "sort_order": 4,
            "pieces": _piece_set([
                ("y2k_bunker_log",  "Bunker Watch Log",     "📓"),
                ("canned_goods",    "Canned Soup Stockpile","🥫"),
                ("battery_pack",    "Battery Pack",         "🔋"),
                ("paper_compliance","Paper Compliance Cert","📜"),
                ("clock_resync",    "Manual Clock Resync",  "⏰"),
                ("backup_tape_dat", "DAT Backup Tape",      "📼"),
                ("flannel_emergency","Emergency Flannel",   "👕"),
                ("noaa_radio",      "NOAA Weather Radio",   "📻"),
                ("disc_install_bsd","BSD Install CD",       "💿"),
                ("pager_text",      "Pager 'all clear' Text","📟"),
                ("y2k_tshirt",      "Limited Y2K T-shirt",  "👕"),
                ("midnight_audit",  "Midnight Audit Receipt","🧾"),
            ], completion_idx=11),
            "reward": {"kind": "currency", "gems": 200, "frame_code": "legen_waitforit_dary_hoarder"},
        },
        # ── 21-40 bracket ─────────────────────────────────────────────────
        {
            "code": "floppy_boneyard",
            "name": "Floppy Drive Boneyard",
            "theme": "Discs that nobody can read anymore.",
            "rarity": "UNCOMMON", "level_bracket": "21-40", "sort_order": 5,
            "pieces": _piece_set([
                ("floppy_525_blue","5.25\" Floppy (Blue)","💾"),
                ("floppy_525_red","5.25\" Floppy (Red)", "💾"),
                ("floppy_35_black","3.5\" Floppy (Black)","💾"),
                ("floppy_35_color","3.5\" Floppy (Rainbow)","💾"),
                ("zip_disk_100",  "Zip Disk 100MB",      "💽"),
                ("jaz_disk_1gb",  "Jaz Disk 1GB",        "💽"),
                ("ls120_super",   "LS-120 SuperDisk",    "💽"),
                ("floppy_label_handwritten","Handwritten Label Floppy","📝"),
            ], completion_idx=7),
            "reward": {"kind": "frame", "frame_code": "floppy_whisperer"},
        },
        {
            "code": "paperclip_anthology",
            "name": "Themed Paperclip Anthology",
            "theme": "Curated by someone who clearly had time.",
            "rarity": "RARE", "level_bracket": "21-40", "sort_order": 6,
            "pieces": _piece_set([
                ("clip_butterfly", "Butterfly Clip",   "🦋"),
                ("clip_owl",       "Owl Clip",         "🦉"),
                ("clip_jumbo_gold","Jumbo Gold Clip",  "📎"),
                ("clip_neon_green","Neon Green Clip",  "📎"),
                ("clip_glitter",   "Glitter Clip",     "✨"),
                ("clip_skull",     "Skull Clip",       "💀"),
                ("clip_holiday",   "Limited Holiday Clip","🎄"),
                ("clip_handmade",  "Handmade Beaded Clip","💎"),
            ], completion_idx=7),
            "reward": {"kind": "currency", "coins": 800, "gems": 80, "shards": 20},
        },
        {
            "code": "server_closet_archaeology",
            "name": "Server Closet Archaeology",
            "theme": "Whatever's been back there since the office moved.",
            "rarity": "EPIC", "level_bracket": "21-40", "sort_order": 7,
            "pieces": _piece_set([
                ("cat5_bent",      "Bent CAT5 Cable",     "🔌"),
                ("ups_dead",       "Dead UPS Battery",    "🔋"),
                ("kvm_old",        "Yellowing KVM",       "🔀"),
                ("dust_bunny_giant","Giant Dust Bunny",   "💨"),
                ("rack_screw",     "Stripped Rack Screw", "🔩"),
                ("ethernet_orange","Orange Crossover",    "🔌"),
                ("label_maker_tape","Old Label Tape Roll","🏷️"),
                ("zip_tie_jungle", "Zip-tie Jungle Cluster","🌿"),
                ("cd_unmarked",    "Unmarked CD-R",       "💿"),
                ("doc_post_it_tower","Tower of Post-its", "📒"),
            ], completion_idx=9),
            "reward": {"kind": "hero_shards", "amount": 30, "rarity": "EPIC"},
        },
        {
            "code": "legendary_rolodex",
            "name": "The Legendary Rolodex",
            "theme": "Index cards from sysadmins past.",
            "rarity": "LEGENDARY", "level_bracket": "21-40", "sort_order": 8,
            "pieces": _piece_set([
                ("card_dba_pete",   "DBA Pete's Card",      "🗂️"),
                ("card_unix_dave",  "Unix Dave's Card",     "🗂️"),
                ("card_security_lin","Security Lin's Card", "🗂️"),
                ("card_helpdesk_kim","Helpdesk Kim's Card", "🗂️"),
                ("card_vendor_acme","Vendor: ACME Card",    "🗂️"),
                ("card_dev_anita",  "Dev Anita's Card",     "🗂️"),
                ("card_oncall_rota","On-call Rotation Card","🗂️"),
                ("card_consultant", "$300/hr Consultant",   "🗂️"),
                ("card_recruiter",  "External Recruiter",   "🗂️"),
                ("card_unknown",    "Card with No Name",    "🗂️"),
                ("card_legend",     "The 'Just Call Mike'", "🗂️"),
                ("card_origin",     "Founder Card (Original)","🗂️"),
            ], completion_idx=11),
            "reward": {"kind": "currency", "gems": 200, "frame_code": "rolodex_keeper"},
        },
        # ── 41-60 bracket ─────────────────────────────────────────────────
        {
            "code": "cassette_oddities",
            "name": "Cassette & 8-track Oddities",
            "theme": "The format wars never really ended.",
            "rarity": "UNCOMMON", "level_bracket": "41-60", "sort_order": 9,
            "pieces": _piece_set([
                ("eight_track_clean","Clean 8-track",     "📼"),
                ("eight_track_warped","Warped 8-track",   "📼"),
                ("cassette_metal",  "Type IV Cassette",   "📼"),
                ("cassette_dat",    "DAT Cassette",       "📼"),
                ("vhs_training",    "VHS Training Tape",  "📼"),
                ("betamax_mystery", "Betamax (Unmarked)", "📼"),
                ("microcassette",   "Microcassette",      "📼"),
                ("reel_to_reel",    "Reel-to-reel Spool", "📼"),
            ], completion_idx=7),
            "reward": {"kind": "frame", "frame_code": "tape_curator"},
        },
        {
            "code": "patch_tuesday_memorial",
            "name": "Patch Tuesday Memorial KBs",
            "theme": "Articles from the long Tuesdays.",
            "rarity": "RARE", "level_bracket": "41-60", "sort_order": 10,
            "pieces": _piece_set([
                ("kb_3024815", "KB3024815 (Reboots)",   "📄"),
                ("kb_4023057", "KB4023057 (Updates)",   "📄"),
                ("kb_legacy",  "KB Legacy 'do not run'","📄"),
                ("kb_hotfix",  "Out-of-band Hotfix",    "📄"),
                ("kb_recall",  "Recalled KB",           "📄"),
                ("kb_security","Critical Security KB",  "📄"),
                ("kb_winter",  "Winter Patch Notes",    "📄"),
                ("kb_orig",    "First Patch Tuesday Memo","📄"),
            ], completion_idx=7),
            "reward": {"kind": "currency", "coins": 1200, "gems": 100, "shards": 30},
        },
        {
            "code": "forbidden_codebase",
            "name": "The Forbidden Codebase",
            "theme": "Don't touch any of this.",
            "rarity": "EPIC", "level_bracket": "41-60", "sort_order": 11,
            "pieces": _piece_set([
                ("cobol_listing",   "COBOL Listing (Yellow)","📜"),
                ("fortran_card",    "Fortran Punch Card",    "🃏"),
                ("perl_oneliner",   "Perl Oneliner (Sacred)","🐪"),
                ("vb6_form",        "VB6 .frm File",         "🪟"),
                ("delphi_pas",      "Delphi .pas Module",    "📜"),
                ("regex_unholy",    "300-char Regex Print",  "📃"),
                ("makefile_cursed", "Cursed Makefile",       "📜"),
                ("classic_asp",     "Classic ASP File",      "📜"),
                ("xslt_template",   "XSLT Transform",        "📜"),
                ("source_locked",   "Locked .tgz Archive",   "📦"),
            ], completion_idx=9),
            "reward": {"kind": "hero_shards", "amount": 30, "rarity": "EPIC"},
        },
        {
            "code": "founders_garage",
            "name": "Founder's Garage",
            "theme": "Original prototype hardware.",
            "rarity": "LEGENDARY", "level_bracket": "41-60", "sort_order": 12,
            "pieces": _piece_set([
                ("pcb_original",    "Original PCB",         "🔧"),
                ("breadboard_jumper","Jumper-wire Tangle",  "🧵"),
                ("schematic_napkin","Napkin Schematic",     "📐"),
                ("scope_polaroid",  "Oscilloscope Polaroid","📸"),
                ("solder_iron_old", "Old Soldering Iron",   "🔥"),
                ("ide_floppy_dev",  "Dev IDE on Floppy",    "💾"),
                ("voltmeter_taped", "Taped Voltmeter",      "🧰"),
                ("chip_unmarked",   "Unmarked DIP Chip",    "🔲"),
                ("fan_homemade",    "Homemade CPU Fan",     "🌀"),
                ("logo_first_sketch","First Logo Sketch",   "✏️"),
                ("press_release_v1","V1 Press Release",     "📰"),
                ("garage_key",      "Garage Front-door Key","🗝️"),
            ], completion_idx=11),
            "reward": {"kind": "currency", "gems": 200, "frame_code": "founders_friend"},
        },
    ]

    added = 0
    for d in DEFS:
        existing = db.get(Collection, d["code"])
        if existing is None:
            db.add(Collection(
                code=d["code"], name=d["name"], theme=d["theme"],
                rarity=d["rarity"], level_bracket=d["level_bracket"],
                pieces_json=json.dumps(d["pieces"]),
                reward_json=json.dumps(d["reward"]),
                sort_order=d["sort_order"],
            ))
            added += 1
        else:
            existing.name = d["name"]
            existing.theme = d["theme"]
            existing.rarity = d["rarity"]
            existing.level_bracket = d["level_bracket"]
            existing.pieces_json = json.dumps(d["pieces"])
            existing.reward_json = json.dumps(d["reward"])
            existing.sort_order = d["sort_order"]
    db.commit()
    return added


def seed() -> None:
    _ensure_schema()
    with SessionLocal() as db:
        from app.rig_map import rig_for as _rig_for

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
                rig=_rig_for(h["code"]),
            ))
            added_h += 1

        # Reconcile rig column on existing rows so updates to rig_map.py
        # propagate without needing a new migration.
        for tpl in db.scalars(select(HeroTemplate)).all():
            desired = _rig_for(tpl.code)
            if tpl.rig != desired:
                tpl.rig = desired

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

            # --- NIGHTMARE tier: same waves, enemies +20 levels, 2.5x rewards, gated on HARD clear.
            nightmare_code = f"N-{s['code']}"
            if nightmare_code not in existing_stage_codes:
                nm_waves = []
                for w in s["waves"]:
                    nm_waves.append({
                        "enemies": [
                            {"template_code": e["template_code"], "level": int(e.get("level", 1)) + 20}
                            for e in w.get("enemies", [])
                        ]
                    })
                db.add(Stage(
                    code=nightmare_code,
                    name=f"{s['name']} (Nightmare)",
                    order=s["order"] + 200,   # keeps HARD sorted before NIGHTMARE
                    energy_cost=s["energy_cost"] + 2,
                    recommended_power=s["recommended_power"] * 3,
                    waves_json=json.dumps(nm_waves),
                    coin_reward=int(s["coin_reward"] * 2.5),
                    first_clear_gems=s["first_clear_gems"] * 3,
                    first_clear_shards=s["first_clear_shards"] * 3,
                    difficulty_tier=StageDifficulty.NIGHTMARE,
                    requires_code=hard_code,
                ))
                added_s += 1

            # --- LEGENDARY tier: same waves, enemies +30 levels, 3.5x rewards, gated on NIGHTMARE clear.
            legendary_code = f"L-{s['code']}"
            if legendary_code not in existing_stage_codes:
                lg_waves = []
                for w in s["waves"]:
                    lg_waves.append({
                        "enemies": [
                            {"template_code": e["template_code"], "level": int(e.get("level", 1)) + 30}
                            for e in w.get("enemies", [])
                        ]
                    })
                db.add(Stage(
                    code=legendary_code,
                    name=f"{s['name']} (Legendary)",
                    order=s["order"] + 300,   # keeps NIGHTMARE sorted before LEGENDARY
                    energy_cost=s["energy_cost"] + 3,
                    recommended_power=s["recommended_power"] * 4,
                    waves_json=json.dumps(lg_waves),
                    coin_reward=int(s["coin_reward"] * 3.5),
                    first_clear_gems=s["first_clear_gems"] * 4,
                    first_clear_shards=s["first_clear_shards"] * 4,
                    difficulty_tier=StageDifficulty.LEGENDARY,
                    requires_code=nightmare_code,
                ))
                added_s += 1

        # Battle Pass — Season 1 idempotent seed + matching shop SKU.
        from app.battle_pass import seed_active_season
        bp_season = seed_active_season(db)
        bp_sku = f"battle_pass_premium_{bp_season.code}"
        if db.scalar(select(ShopProduct).where(ShopProduct.sku == bp_sku)) is None:
            db.add(ShopProduct(
                sku=bp_sku,
                title=f"{bp_season.name} — Premium Pass",
                description=(
                    "Unlock the Premium reward track for the current Battle Pass "
                    "season. Earned XP from gameplay claims rewards on both tracks; "
                    "Premium adds gems, shards, and seasonal milestones at every tier."
                ),
                kind=ShopProductKind.BATTLE_PASS,
                price_cents=bp_season.premium_price_cents,
                contents_json=json.dumps({
                    "battle_pass_premium": True,
                    "battle_pass_season_code": bp_season.code,
                }),
                sort_order=200,
                per_account_limit=1,
                is_active=True,
            ))
        if db.scalar(select(ShopProduct).where(ShopProduct.sku == "monthly_card")) is None:
            db.add(ShopProduct(
                sku="monthly_card",
                title="Monthly Card",
                description=(
                    "30 days of daily 💎 50 gems + 💎 100 instant. "
                    "Stacks: re-purchase extends the card. Best value in the shop."
                ),
                kind=ShopProductKind.SUBSCRIPTION_CARD,
                price_cents=499,
                contents_json=json.dumps({
                    "monthly_card_days": 30,
                    "monthly_card_instant_gems": 100,
                }),
                sort_order=190,
                per_account_limit=0,
                is_active=True,
            ))

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

        added_b = seed_offer_bundles(db)
        added_ga = seed_guild_achievements(db)
        added_c = seed_collections(db)
        db.commit()
        print(f"seeded heroes+={added_h} stages+={added_s} liveops+={added_l} products+={added_p} offer_bundles+={added_b} guild_achievements+={added_ga} collections+={added_c}")


if __name__ == "__main__":
    seed()
