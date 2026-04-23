"""Gear rolling + stat aggregation. Pure."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from app.models import GearRarity, GearSet, GearSlot, HeroInstance


# Main-stat pool per slot (one of these is always present).
MAIN_STAT_BY_SLOT: dict[GearSlot, list[str]] = {
    GearSlot.WEAPON: ["atk"],
    GearSlot.HELMET: ["hp"],
    GearSlot.ARMOR: ["def"],
    GearSlot.BOOTS: ["spd"],
    GearSlot.RING: ["atk", "def", "hp"],
    GearSlot.AMULET: ["atk", "def", "hp"],
}

SUBSTAT_POOL = ["hp", "atk", "def", "spd"]

# Main stat flat values by rarity (scaled bigger for HP because HP numbers are larger).
MAIN_FLAT: dict[str, dict[GearRarity, tuple[int, int]]] = {
    "hp":  {GearRarity.COMMON: (80, 140), GearRarity.RARE: (160, 260), GearRarity.EPIC: (260, 400), GearRarity.LEGENDARY: (400, 600)},
    "atk": {GearRarity.COMMON: (10, 20),  GearRarity.RARE: (20, 40),   GearRarity.EPIC: (40, 65),   GearRarity.LEGENDARY: (60, 90)},
    "def": {GearRarity.COMMON: (10, 20),  GearRarity.RARE: (20, 40),   GearRarity.EPIC: (40, 65),   GearRarity.LEGENDARY: (60, 90)},
    "spd": {GearRarity.COMMON: (1, 3),    GearRarity.RARE: (3, 6),     GearRarity.EPIC: (6, 10),    GearRarity.LEGENDARY: (10, 15)},
}

SUB_FLAT: dict[str, tuple[int, int]] = {
    "hp": (20, 100),
    "atk": (3, 15),
    "def": (3, 15),
    "spd": (1, 4),
}

RARITY_WEIGHTS = {
    GearRarity.COMMON: 0.55,
    GearRarity.RARE: 0.32,
    GearRarity.EPIC: 0.11,
    GearRarity.LEGENDARY: 0.02,
}

# Higher-order stages nudge drops toward better rarity.
STAGE_LUCK_BONUS = 0.03  # per stage order above 1


def roll_rarity(rng: random.Random, stage_order: int = 1) -> GearRarity:
    weights = dict(RARITY_WEIGHTS)
    bump = max(0, stage_order - 1) * STAGE_LUCK_BONUS
    weights[GearRarity.RARE] += bump
    weights[GearRarity.EPIC] += bump * 0.5
    weights[GearRarity.LEGENDARY] += bump * 0.25
    weights[GearRarity.COMMON] = max(0.0, weights[GearRarity.COMMON] - bump * 1.75)
    total = sum(weights.values())
    r = rng.random() * total
    acc = 0.0
    for rarity, w in weights.items():
        acc += w
        if r < acc:
            return rarity
    return GearRarity.COMMON


def roll_gear(
    rng: random.Random, stage_order: int = 1
) -> tuple[GearSlot, GearRarity, GearSet, dict[str, int]]:
    slot = rng.choice(list(GearSlot))
    rarity = roll_rarity(rng, stage_order)
    set_code = rng.choice(list(GearSet))
    main_stat = rng.choice(MAIN_STAT_BY_SLOT[slot])
    lo, hi = MAIN_FLAT[main_stat][rarity]
    stats: dict[str, int] = {main_stat: rng.randint(lo, hi)}
    # Substat count by rarity.
    sub_count = {GearRarity.COMMON: 0, GearRarity.RARE: 1, GearRarity.EPIC: 2, GearRarity.LEGENDARY: 3}[rarity]
    available_subs = [s for s in SUBSTAT_POOL if s != main_stat]
    rng.shuffle(available_subs)
    for sub in available_subs[:sub_count]:
        lo, hi = SUB_FLAT[sub]
        stats[sub] = stats.get(sub, 0) + rng.randint(lo, hi)
    return slot, rarity, set_code, stats


# Passive %-stat sets need 2 pieces; active sets (VIOLENT/LIFESTEAL) need 4.
SET_BONUS_STAT: dict[GearSet, str] = {
    GearSet.VITAL: "hp",
    GearSet.OFFENSE: "atk",
    GearSet.DEFENSE: "def",
    GearSet.SWIFT: "spd",
}
PASSIVE_SET_PIECES = 2
ACTIVE_SET_PIECES = 4
SET_BONUS_PCT = 0.15

# Active set tuning — kept loose so the combat engine can read them.
VIOLENT_EXTRA_TURN_CHANCE = 0.20
LIFESTEAL_FRAC = 0.30

ACTIVE_SETS: set[GearSet] = {GearSet.VIOLENT, GearSet.LIFESTEAL}


def _set_counts(hero: HeroInstance) -> dict[str, int]:
    counts: dict[str, int] = {}
    for g in hero.gear:
        code = str(g.set_code) if g.set_code else ""
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


def gear_bonus_for(hero: HeroInstance) -> dict:
    """Flat bonuses + percentage set bonuses + active-set flags.

    Returns a dict with keys:
        hp, atk, def, spd: flat totals (int)
        pct: {"hp","atk","def","spd": float}
        active: {"violent": bool, "lifesteal": bool}
    """
    total: dict = {
        "hp": 0, "atk": 0, "def": 0, "spd": 0,
        "pct": {"hp": 0.0, "atk": 0.0, "def": 0.0, "spd": 0.0},
        "active": {"violent": False, "lifesteal": False},
    }
    set_counts = _set_counts(hero)
    for g in hero.gear:
        try:
            data = json.loads(g.stats_json or "{}")
        except json.JSONDecodeError:
            continue
        for k, v in data.items():
            if k in total and isinstance(v, (int, float)):
                total[k] += int(v)

    for code, count in set_counts.items():
        try:
            gs = GearSet(code) if not isinstance(code, GearSet) else code
        except ValueError:
            continue
        if gs in ACTIVE_SETS:
            if count >= ACTIVE_SET_PIECES:
                if gs == GearSet.VIOLENT:
                    total["active"]["violent"] = True
                elif gs == GearSet.LIFESTEAL:
                    total["active"]["lifesteal"] = True
        else:
            pieces_completed = count // PASSIVE_SET_PIECES
            if pieces_completed <= 0:
                continue
            stat = SET_BONUS_STAT.get(gs)
            if stat:
                total["pct"][stat] += SET_BONUS_PCT * pieces_completed
    return total


def completed_sets(hero: HeroInstance) -> dict[str, int]:
    """Return {set_code: completed_instances} for inspection.

    Counts active-set activations separately (0 or 1) from passive-set stacks.
    """
    counts = _set_counts(hero)
    out: dict[str, int] = {}
    for code, n in counts.items():
        try:
            gs = GearSet(code) if not isinstance(code, GearSet) else code
        except ValueError:
            continue
        if gs in ACTIVE_SETS:
            if n >= ACTIVE_SET_PIECES:
                out[code] = 1
        else:
            stacks = n // PASSIVE_SET_PIECES
            if stacks > 0:
                out[code] = stacks
    return out
