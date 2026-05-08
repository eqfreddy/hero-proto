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


def test_soft_pity_lifts_epic_rate_above_base() -> None:
    """Players past the soft threshold should hit Epic+ noticeably more often
    than at pity=0, well before the hard floor triggers."""
    base_epic = 0
    soft_epic = 0
    for seed in range(2000):
        rng_a = random.Random(seed)
        rng_b = random.Random(seed * 31 + 7)
        if roll(0, rng_a).pity_triggered or roll(0, rng_a).rarity in (Rarity.EPIC, Rarity.LEGENDARY):
            base_epic += 0  # don't double-count, see below
        # Use independent rolls — fresh rng per call to count epic+ outcomes.
        if roll(0, random.Random(seed)).rarity in (Rarity.EPIC, Rarity.LEGENDARY):
            base_epic += 1
        # Soft pity zone: pity = threshold + 10 → +55% bonus.
        if roll(settings.gacha_soft_pity_threshold + 10, random.Random(seed)).rarity in (Rarity.EPIC, Rarity.LEGENDARY):
            soft_epic += 1
    assert soft_epic > base_epic * 3, f"soft pity should triple the Epic rate; got base={base_epic} soft={soft_epic}"


def test_soft_pity_below_threshold_is_no_op() -> None:
    """At pity=soft_threshold-1 there is no bonus — outcomes equal base rolls."""
    pity = settings.gacha_soft_pity_threshold - 1
    for seed in range(200):
        rng_a = random.Random(seed)
        rng_b = random.Random(seed)
        a = roll(0, rng_a)
        b = roll(pity, rng_b)
        # Both should follow base RATES roll output for the same seed.
        assert a.rarity == b.rarity, f"seed {seed}: base={a.rarity} below-soft={b.rarity}"


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
