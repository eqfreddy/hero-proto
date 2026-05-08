"""Gacha math. Pure functions — no DB writes here."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from app.config import settings
from app.models import Rarity


# --- Stat variance for duplicate summons -----------------------------------
#
# Phase 2.2: when the player pulls a hero they *already own*, roll a small
# per-stat % offset (-VARIANCE_MAX..+VARIANCE_MAX) so dupes aren't
# bit-identical and there's a reason to chase rolls. First copy of a
# template stays vanilla so seeded / starter rosters remain deterministic.

VARIANCE_MAX = 0.10  # ±10% per stat at the extremes
VARIANCE_STATS = ("hp", "atk", "def", "spd")


def roll_variance(rng: random.Random) -> dict[str, float]:
    """Returns a dict {stat: pct} where pct ∈ [-VARIANCE_MAX, +VARIANCE_MAX].
    Distribution is triangular (peak at 0) so most copies cluster near
    nominal but ±10% extremes still happen — gives players something to
    chase without making the average copy feel weak."""
    return {
        s: round(rng.triangular(-VARIANCE_MAX, VARIANCE_MAX, 0.0), 4)
        for s in VARIANCE_STATS
    }


def serialize_variance(pct: dict[str, float]) -> str:
    """JSON-serialize the variance dict, dropping anything outside our
    stat set so we don't persist garbage."""
    cleaned = {s: float(pct.get(s, 0.0) or 0.0) for s in VARIANCE_STATS}
    return json.dumps(cleaned, separators=(",", ":"))


def parse_variance(blob: str | None) -> dict[str, float]:
    """Parse a variance_pct_json blob. Returns {} on empty/malformed.
    Caller treats {} as 'no variance applied' (first copy / pre-Phase-2.2)."""
    if not blob:
        return {}
    try:
        data = json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, float] = {}
    for s in VARIANCE_STATS:
        v = data.get(s)
        if isinstance(v, (int, float)):
            out[s] = max(-VARIANCE_MAX, min(VARIANCE_MAX, float(v)))
    return out

# Rate table (must sum to 1.0).
RATES: list[tuple[Rarity, float]] = [
    (Rarity.COMMON, 0.45),
    (Rarity.UNCOMMON, 0.30),
    (Rarity.RARE, 0.20),
    (Rarity.EPIC, 0.045),
    (Rarity.LEGENDARY, 0.005),
]


@dataclass
class RollResult:
    rarity: Rarity
    pity_triggered: bool
    new_pity: int


def _roll_rarity(rng: random.Random) -> Rarity:
    r = rng.random()
    acc = 0.0
    for rarity, p in RATES:
        acc += p
        if r < acc:
            return rarity
    return RATES[-1][0]  # float safety


def _is_epic_or_better(rarity: Rarity) -> bool:
    return rarity in (Rarity.EPIC, Rarity.LEGENDARY, Rarity.MYTH)


def _soft_pity_epic_bonus(pity_before_this_roll: int) -> float:
    """Additional Epic+ chance applied to this roll based on the current pity
    counter. Returns 0..1.

    Modern gacha standard ("soft pity ramp"):
    - Below the soft threshold: bonus = 0 (base rates apply).
    - Between soft threshold and hard pity: bonus ramps linearly from 0 to
      what the base Epic+ chance plus the bonus would need to be to make
      the EV land an Epic+ before hard pity for ~95% of cohorts.
    - At hard pity: caller short-circuits to a guaranteed Epic upgrade.

    Concretely with defaults (soft=35, hard=50): each pull from 35 onward
    adds +5% chance, so a player at pity=49 has +75% chance on top of base.
    """
    soft = settings.gacha_soft_pity_threshold
    if pity_before_this_roll < soft:
        return 0.0
    over = pity_before_this_roll - soft + 1
    return min(1.0, 0.05 * over)


def roll(pity: int, rng: random.Random) -> RollResult:
    """One gacha pull. `pity` is current pulls-since-last-EPIC+ counter.

    Layers, in order:
    - Base RATES roll.
    - Soft pity bonus rolled separately as 'upgrade to EPIC if hit'.
      Triggered Epic still counts as a pity reset.
    - Hard pity: if the counter reached the threshold and this roll isn't
      EPIC+, force-upgrade to EPIC.
    """
    rolled = _roll_rarity(rng)
    triggered = False

    # Soft pity bonus — players above the soft threshold get an extra Epic
    # roll attached to this pull. Implemented as an independent dice roll
    # against the bonus chance so base RATES stay self-consistent.
    bonus = _soft_pity_epic_bonus(pity)
    if bonus > 0 and not _is_epic_or_better(rolled) and rng.random() < bonus:
        rolled = Rarity.EPIC
        triggered = True

    # Hard pity floor — guaranteed Epic upgrade if we hit the cap.
    if pity + 1 >= settings.gacha_pity_threshold and not _is_epic_or_better(rolled):
        rolled = Rarity.EPIC
        triggered = True

    new_pity = 0 if _is_epic_or_better(rolled) else pity + 1
    return RollResult(rarity=rolled, pity_triggered=triggered, new_pity=new_pity)
