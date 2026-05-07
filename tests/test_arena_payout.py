"""Arena weekly payout distributor — week-key math, reset, distribution."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.arena_payout import (
    current_week_key,
    previous_week_key,
    reset_weekly_counter_if_stale,
)
from app.models import Account


def test_current_week_key_format_iso():
    # 2026-01-05 is a Monday → ISO week 2 of 2026.
    d = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    assert current_week_key(d) == "2026-W02"


def test_current_week_key_year_boundary():
    # 2026-01-01 (Thursday) is still ISO week 1 of 2026.
    d = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert current_week_key(d) == "2026-W01"


def test_previous_week_key_simple():
    d = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)  # ISO week 3
    assert previous_week_key(d) == "2026-W02"


def test_previous_week_key_year_rollover():
    d = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # ISO week 2 → prev = W01 of 2026
    assert previous_week_key(d) == "2026-W01"


def test_reset_weekly_counter_if_stale_zeros_wins_and_bumps_key():
    a = Account(email="r@r", password_hash="x", coins=0, gems=0, shards=0,
                arena_weekly_wins=7, arena_weekly_key="2026-W01")
    now = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)  # week 3
    reset_weekly_counter_if_stale(a, now)
    assert a.arena_weekly_wins == 0
    assert a.arena_weekly_key == "2026-W03"


def test_reset_weekly_counter_no_op_within_same_week():
    a = Account(email="r@r", password_hash="x", coins=0, gems=0, shards=0,
                arena_weekly_wins=4, arena_weekly_key="2026-W03")
    now = datetime(2026, 1, 14, 0, 0, tzinfo=timezone.utc)  # still week 3
    reset_weekly_counter_if_stale(a, now)
    assert a.arena_weekly_wins == 4
    assert a.arena_weekly_key == "2026-W03"


def test_reset_weekly_counter_initializes_empty_key():
    a = Account(email="r@r", password_hash="x", coins=0, gems=0, shards=0,
                arena_weekly_wins=0, arena_weekly_key="")
    now = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)
    reset_weekly_counter_if_stale(a, now)
    assert a.arena_weekly_key == "2026-W03"
    assert a.arena_weekly_wins == 0


def _make_account(db, email, rating, weekly_wins, weekly_key):
    from app.models import Account
    from app.security import hash_password
    a = Account(
        email=email,
        password_hash=hash_password("hunter22"),
        coins=0, gems=0, shards=0,
        arena_rating=rating,
        arena_weekly_wins=weekly_wins,
        arena_weekly_key=weekly_key,
    )
    db.add(a)
    db.flush()
    return a


def test_distribute_pending_pays_top_50_by_rating(client):
    """Distributor ranks accounts by arena_rating and pays per bracket."""
    from app.db import SessionLocal
    from app.arena_payout import distribute_pending, previous_week_key

    # Pin "now" to a Monday so previous_week is unambiguous.
    now = datetime(2026, 1, 12, 0, 30, tzinfo=timezone.utc)  # week 3
    prev_key = previous_week_key(now)

    db = SessionLocal()
    try:
        # 4 accounts with different ratings, all eligible (1+ weekly_wins last week).
        a1 = _make_account(db, "rank1@x", 2000, 5, prev_key)
        a2 = _make_account(db, "rank2@x", 1800, 3, prev_key)
        a3 = _make_account(db, "rank3@x", 1600, 1, prev_key)
        # Ineligible: rating high but 0 wins.
        a4 = _make_account(db, "rank4@x", 1900, 0, prev_key)
        db.commit()

        n = distribute_pending(db, now)
        assert n == 3  # only the 3 eligible accounts paid

        db.refresh(a1)
        db.refresh(a2)
        db.refresh(a3)
        db.refresh(a4)
        # Rank 1 → 500 gems; rank 2-5 → 250; rank 6-20 → 100; rank 21-50 → 50
        assert a1.gems == 500
        assert a2.gems == 250
        assert a3.gems == 250  # rank 3 falls in 2-5 bracket
        assert a4.gems == 0  # ineligible
    finally:
        db.close()


def test_distribute_pending_idempotent(client):
    """Running the distributor twice for the same week is a no-op the second time."""
    from app.db import SessionLocal
    from app.arena_payout import distribute_pending, previous_week_key

    # Use a distinct week (W04) to avoid colliding with the pays-top-50 test (W02).
    now = datetime(2026, 1, 26, 0, 30, tzinfo=timezone.utc)  # week 5, prev = W04
    prev_key = previous_week_key(now)
    db = SessionLocal()
    try:
        _make_account(db, "idemp@x", 2000, 5, prev_key)
        db.commit()
        first = distribute_pending(db, now)
        second = distribute_pending(db, now)
        assert first == 1
        assert second == 0
    finally:
        db.close()


def test_distribute_pending_grants_champion_frame_to_rank_1(client):
    from app.db import SessionLocal
    from app.arena_payout import distribute_pending, previous_week_key
    from app.arena_constants import ARENA_CHAMPION_FRAME

    # Use a distinct week (W05) to avoid colliding with earlier tests.
    now = datetime(2026, 2, 2, 0, 30, tzinfo=timezone.utc)  # week 6, prev = W05
    prev_key = previous_week_key(now)
    db = SessionLocal()
    try:
        a1 = _make_account(db, "champ@x", 2500, 7, prev_key)
        a2 = _make_account(db, "second@x", 2400, 5, prev_key)
        db.commit()
        distribute_pending(db, now)
        db.refresh(a1)
        db.refresh(a2)
        a1_frames = json.loads(a1.cosmetic_frames_json or "[]")
        a2_frames = json.loads(a2.cosmetic_frames_json or "[]")
        assert ARENA_CHAMPION_FRAME in a1_frames
        assert ARENA_CHAMPION_FRAME not in a2_frames
    finally:
        db.close()
