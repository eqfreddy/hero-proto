"""Rest XP — 2x XP multiplier while a rested bank has time remaining.

Bank accumulates during offline periods (capped at 12h) and burns at 2x
wallclock during active sessions (last tick within 5 min). The multiplier
applies to both account-level XP and hero XP grants.

Two entry points:
- update_bank(account, now): per-request tick, mutates the bank based on
  elapsed time since the last tick. Caller commits the row.
- apply_multiplier(account, base_amount): returns scaled XP if bank > 0,
  unchanged otherwise. Does NOT itself burn the bank — burn happens via
  update_bank on the next request.
"""
from __future__ import annotations

from datetime import datetime

from app.models import Account

BANK_CAP_SECONDS = 12 * 3600        # 12 h
OFFLINE_RATE = 1.0                  # 1 banked second per offline second
BURN_RATE = 2.0                     # bank ticks down at 2x wallclock when active
IDLE_THRESHOLD_SECONDS = 5 * 60     # 5 min — past this, treat as offline
MULTIPLIER = 2.0                    # XP grants doubled while bank > 0


def update_bank(account: Account, now: datetime) -> None:
    """Update banked seconds based on elapsed time since the last tick.
    Mutates account in place; caller commits."""
    last = account.rest_xp_last_tick_at
    if last is None:
        account.rest_xp_last_tick_at = now
        return
    elapsed = (now - last).total_seconds()
    if elapsed <= 0:
        account.rest_xp_last_tick_at = now
        return
    if elapsed > IDLE_THRESHOLD_SECONDS:
        added = int(elapsed * OFFLINE_RATE)
        account.rest_xp_banked_seconds = min(
            BANK_CAP_SECONDS,
            int(account.rest_xp_banked_seconds or 0) + added,
        )
    else:
        burn = int(elapsed * BURN_RATE)
        account.rest_xp_banked_seconds = max(
            0,
            int(account.rest_xp_banked_seconds or 0) - burn,
        )
    account.rest_xp_last_tick_at = now


def apply_multiplier(account: Account, base_amount: int) -> int:
    """Return the XP grant amount scaled by the rest multiplier when the
    bank has time remaining. Returns base_amount unchanged when bank is empty.
    Does NOT itself burn the bank — burn happens via update_bank on the next
    request, decoupling grant logic from time tracking."""
    if int(account.rest_xp_banked_seconds or 0) > 0:
        return int(round(base_amount * MULTIPLIER))
    return base_amount
