"""Drop-meter engine.

Each (stage_code, difficulty_tier) accumulates a per-account counter on every
WIN. When the counter reaches DROP_METER_CAP, the same run that hits the cap
triggers a guaranteed RARE+ drop with tier-keyed rarity weights, then the
counter resets to 0.

State lives on Account.stage_drop_pity_json:
  {"<stage_code>:<TIER>": int}

The helpers do not commit — caller owns the transaction. force_rarity() is a
pure function (RNG -> GearRarity).
"""
from __future__ import annotations

import json
import logging
import random

from app.models import Account, GearRarity, StageDifficulty

log = logging.getLogger(__name__)

DROP_METER_CAP = 20

# Per-tier rarity pool for the guaranteed drop. Weights normalize to 1.0 per tier.
GUARANTEE_POOL: dict[StageDifficulty, dict[GearRarity, float]] = {
    StageDifficulty.NORMAL:    {GearRarity.RARE: 1.0},
    StageDifficulty.HARD:      {GearRarity.RARE: 0.7, GearRarity.EPIC: 0.3},
    StageDifficulty.NIGHTMARE: {GearRarity.EPIC: 0.8, GearRarity.LEGENDARY: 0.2},
    StageDifficulty.LEGENDARY: {GearRarity.EPIC: 0.4, GearRarity.LEGENDARY: 0.6},
}


def _key(stage_code: str, tier: StageDifficulty | str) -> str:
    tier_str = tier.value if isinstance(tier, StageDifficulty) else str(tier)
    return f"{stage_code}:{tier_str}"


def _load(account: Account) -> dict:
    try:
        return json.loads(account.stage_drop_pity_json or "{}")
    except (json.JSONDecodeError, TypeError):
        log.warning("stage_drop_pity_json corrupt for account=%s; resetting", account.id)
        return {}


def _save(account: Account, data: dict) -> None:
    account.stage_drop_pity_json = json.dumps(data)


def read_meter(account: Account, stage_code: str, tier: StageDifficulty | str) -> int:
    """Return the current run-count for a (stage, tier) pair. Defaults to 0."""
    data = _load(account)
    return int(data.get(_key(stage_code, tier), 0))


def increment_and_check(account: Account, stage_code: str, tier: StageDifficulty | str) -> bool:
    """Increment the meter for this (stage, tier) WIN. Returns True when this run
    hits DROP_METER_CAP — caller should force a guaranteed drop. Resets the counter
    to 0 on trigger; otherwise persists the incremented value."""
    data = _load(account)
    key = _key(stage_code, tier)
    new_count = int(data.get(key, 0)) + 1
    if new_count >= DROP_METER_CAP:
        data.pop(key, None)
        _save(account, data)
        return True
    data[key] = new_count
    _save(account, data)
    return False


def force_rarity(tier: StageDifficulty | str, rng: random.Random) -> GearRarity:
    """Weighted pick from the tier's GUARANTEE_POOL. Falls back to RARE if the
    tier is unknown — defensive default."""
    try:
        key = tier if isinstance(tier, StageDifficulty) else StageDifficulty(tier)
    except ValueError:
        return GearRarity.RARE
    pool = GUARANTEE_POOL.get(key)
    if not pool:
        return GearRarity.RARE
    rarities = list(pool.keys())
    weights = [pool[r] for r in rarities]
    return rng.choices(rarities, weights=weights, k=1)[0]
