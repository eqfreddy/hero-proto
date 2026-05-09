"""Tier-lock + power-floor tests."""
from app.models import StageDifficulty
from app.tiers import TIER_POWER_FLOOR, tier_power_floor


def test_power_floor_constants():
    assert TIER_POWER_FLOOR[StageDifficulty.NIGHTMARE] == 50_000
    assert TIER_POWER_FLOOR[StageDifficulty.LEGENDARY] == 100_000
    # NORMAL and HARD have no floor.
    assert StageDifficulty.NORMAL not in TIER_POWER_FLOOR
    assert StageDifficulty.HARD not in TIER_POWER_FLOOR


def test_tier_power_floor_helper():
    assert tier_power_floor(StageDifficulty.NORMAL) is None
    assert tier_power_floor(StageDifficulty.HARD) is None
    assert tier_power_floor(StageDifficulty.NIGHTMARE) == 50_000
    assert tier_power_floor(StageDifficulty.LEGENDARY) == 100_000
    # String inputs accepted (for symmetry with xp_per_win).
    assert tier_power_floor("NIGHTMARE") == 50_000
    assert tier_power_floor("BOGUS") is None
    assert tier_power_floor("") is None
