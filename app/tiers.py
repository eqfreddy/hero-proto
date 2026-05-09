"""Per-tier policy constants and helpers.

Lives separately from app/account_level.py (which owns XP-only concerns)
so each future progression subsystem (fail pity, drop meter) has a
single home for its tier-keyed knobs.
"""
from __future__ import annotations

from app.models import StageDifficulty

# Minimum team power required to start a battle at the given tier.
# Tiers absent from this dict have no floor.
TIER_POWER_FLOOR: dict[StageDifficulty, int] = {
    StageDifficulty.NIGHTMARE: 50_000,
    StageDifficulty.LEGENDARY: 100_000,
}


def tier_power_floor(tier: StageDifficulty | str) -> int | None:
    """Return the minimum team power for a tier, or None if no floor applies.
    Accepts enum or string. Returns None for unknown tiers."""
    try:
        key = tier if isinstance(tier, StageDifficulty) else StageDifficulty(tier)
    except ValueError:
        return None
    return TIER_POWER_FLOOR.get(key)
