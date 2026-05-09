"""Fail-pity engine.

After 3 consecutive losses on a (stage, tier), the next attempt fights with
-10% enemy HP. Counter resets on any win. Hidden mechanic — never shown.

State lives in Account.stage_pity_json:
  {
    "<stage_code>:<TIER>": int,            # consecutive-loss count
    "<stage_code>:<TIER>:_consumed": bool, # discount was applied this cycle
  }

The three exposed entry points are pure read/mutate functions on the
Account row. Caller is responsible for the DB commit; we never commit
here so battle-resolve can stage all its writes in one transaction.
"""
from __future__ import annotations

import json
import logging

from app.models import Account, StageDifficulty

log = logging.getLogger(__name__)

PITY_LOSS_THRESHOLD = 3   # losses before discount kicks in
PITY_HP_MULT = 0.9        # enemy HP multiplier on the discounted attempt


def _key(stage_code: str, tier: StageDifficulty | str) -> str:
    tier_str = tier.value if isinstance(tier, StageDifficulty) else str(tier)
    return f"{stage_code}:{tier_str}"


def _consumed_key(stage_code: str, tier: StageDifficulty | str) -> str:
    return _key(stage_code, tier) + ":_consumed"


def _load(account: Account) -> dict:
    try:
        return json.loads(account.stage_pity_json or "{}")
    except (json.JSONDecodeError, TypeError):
        log.warning("stage_pity_json corrupt for account=%s; resetting", account.id)
        return {}


def _save(account: Account, data: dict) -> None:
    account.stage_pity_json = json.dumps(data)


def read_pity(account: Account, stage_code: str, tier: StageDifficulty | str) -> tuple[int, bool]:
    """Return (count, consumed) for a (stage, tier) pity entry. Defaults (0, False)."""
    data = _load(account)
    count = int(data.get(_key(stage_code, tier), 0))
    consumed = bool(data.get(_consumed_key(stage_code, tier), False))
    return count, consumed


def apply_battle_start(account: Account, stage_code: str, tier: StageDifficulty | str) -> float:
    """Called before the wave loop runs. Returns the enemy-HP multiplier
    (1.0 for no discount, PITY_HP_MULT for discounted). Sets _consumed=True
    on the account row when a discount fires."""
    count, consumed = read_pity(account, stage_code, tier)
    if count >= PITY_LOSS_THRESHOLD and not consumed:
        data = _load(account)
        data[_consumed_key(stage_code, tier)] = True
        _save(account, data)
        return PITY_HP_MULT
    return 1.0


def apply_battle_end(account: Account, stage_code: str, tier: StageDifficulty | str, won: bool) -> None:
    """Called after the final outcome is known. Mutates pity state per spec:
      WIN → clear both keys for this (stage, tier).
      LOSS w/ consumed=True → reset count to 0, clear _consumed.
      LOSS w/ consumed=False → increment count by 1.
    """
    data = _load(account)
    key = _key(stage_code, tier)
    ckey = _consumed_key(stage_code, tier)

    if won:
        data.pop(key, None)
        data.pop(ckey, None)
    else:
        consumed = bool(data.get(ckey, False))
        if consumed:
            # Discount didn't save them — reset cycle.
            data.pop(key, None)
            data.pop(ckey, None)
        else:
            current = int(data.get(key, 0))
            data[key] = current + 1

    _save(account, data)
