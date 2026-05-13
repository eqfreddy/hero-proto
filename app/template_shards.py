"""Per-template shard currency for hero ascension.

Solves the 'what do I do with duplicate pulls' problem. Every dupe summon
auto-grants shards of that hero's template; players spend shards to
ascend the hero (alternative to feeding whole duplicates).

Costs scale per-target-star — going 5★→6★ requires 5x the shards of 1★→2★.
"""
from __future__ import annotations

import json
from typing import Iterable

from app.models import Account, Rarity

# Shards granted on a duplicate pull, keyed by template rarity.
SHARDS_ON_DUPE: dict[Rarity, int] = {
    Rarity.COMMON: 10,
    Rarity.UNCOMMON: 15,
    Rarity.RARE: 25,
    Rarity.EPIC: 50,
    Rarity.LEGENDARY: 100,
    Rarity.MYTH: 200,
}

# Shards needed to ascend FROM the given star tier to the next one.
# 1->2: 10, 2->3: 30, 3->4: 80, 4->5: 200, 5->6: 500.
SHARDS_TO_ASCEND_FROM: dict[int, int] = {
    1: 10, 2: 30, 3: 80, 4: 200, 5: 500,
}

# Shards needed to skill-up FROM the given special_level to the next.
# Replaces the fodder-based model after the 2026-05-12 shard remap.
# Cheap early, steep at cap so the final point feels earned.
SHARDS_TO_SKILL_UP: dict[int, int] = {
    1: 5, 2: 15, 3: 40, 4: 100,
}


def _load(account: Account) -> dict[str, int]:
    try:
        data = json.loads(account.template_shards_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v or 0) for k, v in data.items() if v}


def _save(account: Account, shards: dict[str, int]) -> None:
    cleaned = {k: int(v) for k, v in shards.items() if int(v) > 0}
    account.template_shards_json = json.dumps(cleaned, separators=(",", ":"))


def get_shards(account: Account, template_code: str) -> int:
    return _load(account).get(template_code, 0)


def get_all_shards(account: Account) -> dict[str, int]:
    return _load(account)


def grant(account: Account, template_code: str, amount: int) -> int:
    if amount <= 0:
        return get_shards(account, template_code)
    shards = _load(account)
    shards[template_code] = shards.get(template_code, 0) + int(amount)
    _save(account, shards)
    return shards[template_code]


def spend(account: Account, template_code: str, amount: int) -> bool:
    if amount <= 0:
        return True
    shards = _load(account)
    have = shards.get(template_code, 0)
    if have < amount:
        return False
    shards[template_code] = have - amount
    _save(account, shards)
    return True


def shards_for_ascension(stars: int) -> int | None:
    """Returns shards needed to go from `stars` to `stars+1`, or None at cap."""
    return SHARDS_TO_ASCEND_FROM.get(stars)


def shards_for_skill_up(special_level: int) -> int | None:
    """Returns shards needed to go from `special_level` to `special_level+1`,
    or None at cap. Mirrors the ascension helper signature."""
    return SHARDS_TO_SKILL_UP.get(special_level)


def grant_dupe_shards(account: Account, template_code: str, rarity: Rarity) -> int:
    """Auto-grant shards on a duplicate pull. Returns the new shard balance
    for this template, or 0 if the rarity has no entry."""
    amount = SHARDS_ON_DUPE.get(rarity, 0)
    if amount <= 0:
        return get_shards(account, template_code)
    return grant(account, template_code, amount)
