"""Tests for the AFK income loop."""
from __future__ import annotations

from datetime import timedelta

from tests.conftest import *  # noqa


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json().get("account_id")


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _set_last_collected(email: str, days_ago: float) -> None:
    """Backdate afk_last_collected_at by N days for a given account email."""
    from app.db import SessionLocal
    from app.models import Account, utcnow
    with SessionLocal() as db:
        a = db.query(Account).filter_by(email=email).one()
        a.afk_last_collected_at = utcnow() - timedelta(days=days_ago)
        db.commit()


def test_status_for_new_account_pending_zero(client):
    token, _ = _register(client, "afk_new@example.com")
    r = client.get("/afk", headers=_hdr(token))
    assert r.status_code == 200
    s = r.json()
    # New account, no time elapsed: pending should be ~0.
    assert s["pending_coins"] == 0
    assert s["pending_hero_xp"] == 0
    assert s["coins_per_hour"] >= 150
    assert s["hours_max"] == 12


def test_pending_caps_at_max_hours(client):
    token, _ = _register(client, "afk_cap@example.com")
    _set_last_collected("afk_cap@example.com", days_ago=2)  # 48h far over the 12h cap
    s = client.get("/afk", headers=_hdr(token)).json()
    assert s["is_at_cap"] is True
    # 12h * 150 c/h base = 1800 coins for a level-1 account.
    assert s["pending_coins"] == 1800


def test_claim_grants_coins_and_resets_timer(client):
    token, _ = _register(client, "afk_claim@example.com")
    _set_last_collected("afk_claim@example.com", days_ago=0.5)  # 12h on the dot
    me_before = client.get("/me", headers=_hdr(token)).json()
    r = client.post("/afk/claim", headers=_hdr(token))
    assert r.status_code == 200, r.text
    granted = r.json()
    assert granted["coins"] >= 1700  # ~12h * 150 — leave a small floor for clock drift
    me_after = client.get("/me", headers=_hdr(token)).json()
    assert me_after["coins"] == me_before["coins"] + granted["coins"]

    # Pending immediately after claim should be ~0.
    s = client.get("/afk", headers=_hdr(token)).json()
    assert s["pending_coins"] == 0


def test_claim_with_no_pending_is_zero_grant(client):
    token, _ = _register(client, "afk_empty@example.com")
    # Claim immediately — no time passed.
    r = client.post("/afk/claim", headers=_hdr(token))
    assert r.status_code == 200
    granted = r.json()
    assert granted["coins"] == 0
    assert granted["hero_xp"] == 0


def test_higher_account_level_higher_rate(client):
    token, _ = _register(client, "afk_lvl@example.com")
    base = client.get("/afk", headers=_hdr(token)).json()["coins_per_hour"]
    # Push account to level 5.
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.query(Account).filter_by(email="afk_lvl@example.com").one()
        a.account_level = 5
        db.commit()
    boosted = client.get("/afk", headers=_hdr(token)).json()["coins_per_hour"]
    assert boosted > base
