"""Rest-XP tests."""
from datetime import datetime, timedelta

from app.models import Account
from app.rest_xp import (
    update_bank,
    apply_multiplier,
    BANK_CAP_SECONDS,
    OFFLINE_RATE,
    BURN_RATE,
    IDLE_THRESHOLD_SECONDS,
    MULTIPLIER,
)
from app.models import utcnow


def _make_account(db_session, banked: int = 0, last_tick=None):
    from app.models import Account
    n = db_session.info.get("counter", 0)
    db_session.info["counter"] = n + 1
    acc = Account(
        email=f"rest_{n}@example.com",
        password_hash="x",
        rest_xp_banked_seconds=banked,
        rest_xp_last_tick_at=last_tick or utcnow(),
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def test_account_has_rest_xp_columns(db_session):
    """New accounts get rest_xp_banked_seconds=0 and rest_xp_last_tick_at set to ~now."""
    before = datetime.utcnow()
    acc = Account(email="rest_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.rest_xp_banked_seconds == 0
    assert acc.rest_xp_last_tick_at is not None
    delta = abs((acc.rest_xp_last_tick_at - before).total_seconds())
    assert delta < 5, f"rest_xp_last_tick_at default too far from now: delta={delta}"


def test_constants_match_spec():
    assert BANK_CAP_SECONDS == 12 * 3600
    assert OFFLINE_RATE == 1.0
    assert BURN_RATE == 2.0
    assert IDLE_THRESHOLD_SECONDS == 5 * 60
    assert MULTIPLIER == 2.0


def test_update_bank_offline_period_accumulates(db_session):
    four_hours_ago = utcnow() - timedelta(hours=4)
    acc = _make_account(db_session, banked=0, last_tick=four_hours_ago)
    now = utcnow()
    update_bank(acc, now)
    assert 14000 <= acc.rest_xp_banked_seconds <= 14500
    assert acc.rest_xp_last_tick_at == now


def test_update_bank_caps_at_12h(db_session):
    day_ago = utcnow() - timedelta(hours=24)
    acc = _make_account(db_session, banked=0, last_tick=day_ago)
    update_bank(acc, utcnow())
    assert acc.rest_xp_banked_seconds == BANK_CAP_SECONDS


def test_update_bank_active_session_burns_at_2x(db_session):
    one_min_ago = utcnow() - timedelta(seconds=60)
    acc = _make_account(db_session, banked=1000, last_tick=one_min_ago)
    update_bank(acc, utcnow())
    # 60s × 2 = 120 burned. ±5s slack.
    assert 870 <= acc.rest_xp_banked_seconds <= 885


def test_update_bank_active_burn_floors_at_zero(db_session):
    one_min_ago = utcnow() - timedelta(seconds=60)
    acc = _make_account(db_session, banked=10, last_tick=one_min_ago)
    update_bank(acc, utcnow())
    assert acc.rest_xp_banked_seconds == 0


def test_update_bank_idle_threshold_treats_as_offline(db_session):
    six_min_ago = utcnow() - timedelta(minutes=6)
    acc = _make_account(db_session, banked=100, last_tick=six_min_ago)
    update_bank(acc, utcnow())
    assert acc.rest_xp_banked_seconds > 100


def test_apply_multiplier_with_bank_doubles(db_session):
    acc = _make_account(db_session, banked=1000)
    assert apply_multiplier(acc, 12) == 24
    assert apply_multiplier(acc, 0) == 0
    assert apply_multiplier(acc, 100) == 200


def test_apply_multiplier_no_bank_returns_unchanged(db_session):
    acc = _make_account(db_session, banked=0)
    assert apply_multiplier(acc, 12) == 12
    assert apply_multiplier(acc, 100) == 100


import json


def test_grant_xp_doubles_with_rest_bank(db_session):
    """grant_xp internally applies the rest-XP multiplier."""
    from app.account_level import grant_xp

    acc = _make_account(db_session, banked=1000)
    acc.account_level = 1
    acc.account_xp = 0
    db_session.flush()

    grant_xp(db_session, acc, 12)
    assert acc.account_xp == 24


def test_grant_xp_no_doubling_without_rest_bank(db_session):
    """grant_xp acts as before when bank is empty."""
    from app.account_level import grant_xp

    acc = _make_account(db_session, banked=0)
    acc.account_level = 1
    acc.account_xp = 0
    db_session.flush()

    grant_xp(db_session, acc, 12)
    assert acc.account_xp == 12


def test_get_current_account_ticks_bank(client, db_session):
    """An authenticated request triggers update_bank via the auth dep."""
    from datetime import timedelta
    from app.models import Account
    from app.security import issue_token

    six_min_ago = utcnow() - timedelta(minutes=6)
    acc = Account(
        email="tick_via_auth@example.com",
        password_hash="x",
        rest_xp_banked_seconds=0,
        rest_xp_last_tick_at=six_min_ago,
    )
    db_session.add(acc)
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    db_session.refresh(acc)
    # 6 min offline gap → bank should have accumulated.
    assert acc.rest_xp_banked_seconds > 0
    delta = (utcnow() - acc.rest_xp_last_tick_at).total_seconds()
    assert delta < 5
