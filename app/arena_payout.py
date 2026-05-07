"""Arena weekly leaderboard payout — distributor, week-key math, reset.

The distributor is intentionally lazy: it runs on `/me` hits via
`distribute_pending(db)`. Idempotency is enforced by the
`(week_key, account_id)` composite primary key on `arena_weekly_payouts`.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.arena_constants import ARENA_CHAMPION_FRAME, ARENA_WEEKLY_PAYOUT
from app.models import Account, ArenaWeeklyPayout, utcnow


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


def _gems_for_rank(rank: int) -> int:
    """Map a 1-indexed rank to gems via ARENA_WEEKLY_PAYOUT brackets. 0 if unranked."""
    for lo, hi, gems in ARENA_WEEKLY_PAYOUT:
        if lo <= rank <= hi:
            return gems
    return 0


def _max_paid_rank() -> int:
    return max(hi for _, hi, _ in ARENA_WEEKLY_PAYOUT)


def distribute_pending(db: Session, now: datetime | None = None) -> int:
    """Distribute prior-week payouts. Returns count of new payout rows inserted.

    Idempotent: if any ArenaWeeklyPayout row exists for the prior week, this
    is a no-op (returns 0).

    Algorithm:
      1. Compute previous_week_key from `now`.
      2. Check existing rows for that week_key — if any, return 0.
      3. Snapshot top-N (N = max paid rank) accounts by arena_rating where
         arena_weekly_wins >= 1 AND arena_weekly_key == previous_week_key.
      4. For each, INSERT ArenaWeeklyPayout, credit gems, grant champion frame
         to rank 1 if not already held.
      5. Commit.
    """
    n = now or utcnow()
    prev_key = previous_week_key(n)

    # Idempotency check: if any payout row exists for prev_key, bail.
    existing = db.execute(
        select(ArenaWeeklyPayout.account_id)
        .where(ArenaWeeklyPayout.week_key == prev_key)
        .limit(1)
    ).first()
    if existing is not None:
        return 0

    eligible = list(db.execute(
        select(Account)
        .where(
            Account.arena_weekly_wins >= 1,
            Account.arena_weekly_key == prev_key,
        )
        .order_by(Account.arena_rating.desc(), Account.id.asc())
        .limit(_max_paid_rank())
    ).scalars())

    inserted = 0
    for idx, account in enumerate(eligible):
        rank = idx + 1
        gems = _gems_for_rank(rank)
        if gems == 0:
            continue
        payout = ArenaWeeklyPayout(
            week_key=prev_key,
            account_id=account.id,
            rank=rank,
            gems=gems,
            eligible_wins=account.arena_weekly_wins,
        )
        db.add(payout)
        try:
            db.flush()
        except IntegrityError:
            # Another caller raced us. Roll back this row only and continue.
            db.rollback()
            continue
        account.gems = (account.gems or 0) + gems
        if rank == 1:
            try:
                frames = json.loads(account.cosmetic_frames_json or "[]")
            except json.JSONDecodeError:
                frames = []
            if ARENA_CHAMPION_FRAME not in frames:
                frames.append(ARENA_CHAMPION_FRAME)
                account.cosmetic_frames_json = json.dumps(frames)
        inserted += 1

    db.commit()
    return inserted
