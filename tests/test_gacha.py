"""Pure unit tests for the gacha math."""

from __future__ import annotations

import random

from app.config import settings
from app.gacha import roll
from app.models import Rarity


def test_pity_triggers_on_threshold() -> None:
    rng = random.Random(1)
    # Force common-weighted rolls by seeding high (>0.55 cum for COMMON).
    pity = settings.gacha_pity_threshold - 1
    result = roll(pity, rng)
    # One more pull after this should hit pity if it doesn't naturally roll EPIC+.
    assert 0 <= result.new_pity
    # The very next pull from a state of (threshold-1) will either happen naturally or upgrade.
    if not result.pity_triggered:
        # Not yet triggered — do another pull with the updated counter.
        result2 = roll(result.new_pity, rng)
        assert result2.pity_triggered or result2.rarity in (Rarity.EPIC, Rarity.LEGENDARY)


def test_rarity_counter_resets_on_epic_plus() -> None:
    rng = random.Random(42)
    result = roll(0, rng)
    if result.rarity in (Rarity.EPIC, Rarity.LEGENDARY):
        assert result.new_pity == 0
    else:
        assert result.new_pity == 1


def test_distribution_is_sane_over_many_pulls() -> None:
    rng = random.Random(12345)
    pity = 0
    hist: dict[Rarity, int] = {r: 0 for r in Rarity}
    for _ in range(2000):
        r = roll(pity, rng)
        hist[r.rarity] += 1
        pity = r.new_pity
    # Common-dominant, legendary rare. Exact ratios drift with RNG but bounds hold.
    assert hist[Rarity.COMMON] > hist[Rarity.UNCOMMON] > hist[Rarity.RARE]
    assert hist[Rarity.LEGENDARY] < hist[Rarity.EPIC]
