"""Arena weekly payout distributor — week-key math, reset, distribution."""
from __future__ import annotations

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
