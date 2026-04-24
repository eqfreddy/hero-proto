"""Daily login bonus / streak logic. Pure functions — no I/O, no commits.

The cycle is 7 days. Each day has a fixed reward; day 7 is the big payout
(gems + access cards) so players have a reason to maintain the streak. After
7 days the cycle repeats from day 1 — streak keeps accumulating but the reward
table wraps via modulo.

A claim is valid if the account has never claimed, or the last claim was more
than 20h ago (slightly under 24 to be user-friendly at session boundaries).
If more than 48h ago, streak resets to 1 (missed a day).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import Account, utcnow

CLAIM_COOLDOWN_HOURS = 20       # min between claims
STREAK_RESET_HOURS = 48         # beyond this, streak resets to 1


@dataclass
class DailyReward:
    coins: int = 0
    gems: int = 0
    shards: int = 0
    access_cards: int = 0


# Day-in-cycle (1-indexed) -> reward. Day 7 is the "big day" payout.
_REWARD_TABLE: dict[int, DailyReward] = {
    1: DailyReward(coins=200),
    2: DailyReward(coins=300, shards=2),
    3: DailyReward(gems=25),
    4: DailyReward(coins=500, shards=5),
    5: DailyReward(gems=50),
    6: DailyReward(coins=800, shards=10),
    7: DailyReward(gems=200, access_cards=3),
}


def reward_for_streak(streak: int) -> DailyReward:
    """Look up the reward for a streak value. Wraps on 7-day cycle."""
    if streak < 1:
        streak = 1
    idx = ((streak - 1) % 7) + 1
    return _REWARD_TABLE[idx]


def _hours_since(ts: datetime | None, now: datetime) -> float | None:
    if ts is None:
        return None
    return (now - ts).total_seconds() / 3600.0


@dataclass
class ClaimResult:
    granted: DailyReward
    streak_after: int
    next_claim_at: datetime
    was_reset: bool


def can_claim(account: Account, now: datetime | None = None) -> tuple[bool, datetime | None]:
    """Returns (can_claim_now, next_claim_at). next_claim_at is None when claim is available."""
    now = now or utcnow()
    if account.last_daily_claim_at is None:
        return True, None
    hours = _hours_since(account.last_daily_claim_at, now)
    if hours is None or hours >= CLAIM_COOLDOWN_HOURS:
        return True, None
    return False, account.last_daily_claim_at + timedelta(hours=CLAIM_COOLDOWN_HOURS)


def preview_next_streak(account: Account, now: datetime | None = None) -> int:
    """What streak value *would* result from a claim right now? Used for UI preview."""
    now = now or utcnow()
    hours = _hours_since(account.last_daily_claim_at, now)
    if hours is None or hours >= STREAK_RESET_HOURS:
        return 1
    return account.daily_streak + 1


def apply_claim(account: Account, now: datetime | None = None) -> ClaimResult:
    """Mutate the account: increment streak (or reset), grant reward. Caller commits."""
    now = now or utcnow()
    hours = _hours_since(account.last_daily_claim_at, now)
    was_reset = False
    if hours is None or hours >= STREAK_RESET_HOURS:
        account.daily_streak = 1
        was_reset = account.last_daily_claim_at is not None
    else:
        account.daily_streak += 1

    reward = reward_for_streak(account.daily_streak)
    account.coins += reward.coins
    account.gems += reward.gems
    account.shards += reward.shards
    account.access_cards += reward.access_cards
    account.last_daily_claim_at = now
    return ClaimResult(
        granted=reward,
        streak_after=account.daily_streak,
        next_claim_at=now + timedelta(hours=CLAIM_COOLDOWN_HOURS),
        was_reset=was_reset,
    )
