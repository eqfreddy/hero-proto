"""Arena weekly leaderboard payout — distributor, week-key math, reset.

The distributor is intentionally lazy: it runs on `/me` hits via
`distribute_pending(db)`. Idempotency is enforced by the
`(week_key, account_id)` composite primary key on `arena_weekly_payouts`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Account, utcnow


def current_week_key(now: datetime | None = None) -> str:
    """ISO week key, e.g. '2026-W19'. Always uses the date's ISO calendar."""
    n = now or utcnow()
    iso_year, iso_week, _ = n.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def previous_week_key(now: datetime | None = None) -> str:
    """Week key for 7 days before `now`. Subtracting a week and re-keying is
    safer than week_number - 1 (which breaks across year boundaries)."""
    n = now or utcnow()
    return current_week_key(n - timedelta(days=7))


def reset_weekly_counter_if_stale(account: Account, now: datetime | None = None) -> None:
    """Bump the per-account weekly key + zero its wins counter if the stored
    key is stale or empty. Cheap (string compare) — call freely.
    """
    key = current_week_key(now)
    if account.arena_weekly_key != key:
        account.arena_weekly_wins = 0
        account.arena_weekly_key = key
