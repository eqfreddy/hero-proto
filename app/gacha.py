"""Gacha math. Pure functions — no DB writes here."""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.config import settings
from app.models import Rarity

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
    return rarity in (Rarity.EPIC, Rarity.LEGENDARY)


def roll(pity: int, rng: random.Random) -> RollResult:
    """One gacha pull. `pity` is current pulls-since-last-EPIC+ counter.

    Pity: if the counter reached the threshold and this roll isn't EPIC+, upgrade to EPIC.
    """
    rolled = _roll_rarity(rng)
    triggered = False
    if pity + 1 >= settings.gacha_pity_threshold and not _is_epic_or_better(rolled):
        rolled = Rarity.EPIC
        triggered = True

    new_pity = 0 if _is_epic_or_better(rolled) else pity + 1
    return RollResult(rarity=rolled, pity_triggered=triggered, new_pity=new_pity)
