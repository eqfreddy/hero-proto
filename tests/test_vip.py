"""Tests for VIP tiers + perk integration."""
from __future__ import annotations

from tests.conftest import *  # noqa


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def test_new_account_is_vip_zero(client):
    token = _register(client, "vip_new@example.com")
    r = client.get("/vip", headers=_hdr(token)).json()
    assert r["level"] == 0
    assert r["xp"] == 0
    assert r["xp_to_next"] == 100  # tier 1 threshold
    assert r["next_label"] == "Bronze"
    assert r["perks"]["afk_cap_hours"] == 12
    assert r["perks"]["daily_drip_gems"] == 0


def test_purchase_grants_vip_xp(client):
    token = _register(client, "vip_buy@example.com")
    # Buy the monthly card ($4.99 = 499 cents).
    r = client.post("/shop/purchases", json={"sku": "monthly_card"}, headers=_hdr(token))
    assert r.status_code == 201, r.text
    vip = client.get("/vip", headers=_hdr(token)).json()
    assert vip["xp"] >= 499
    assert vip["level"] >= 1  # 100c threshold met


def test_vip_extends_afk_cap(client):
    token = _register(client, "vip_afk@example.com")
    # AFK cap is 12h before purchase.
    afk_before = client.get("/afk", headers=_hdr(token)).json()
    assert afk_before["hours_max"] == 12

    # Buy enough to hit VIP 3 (>= 2000c). Stack two BP purchases ($9.99 each = 1998c)
    # plus monthly card (499c) = 2497c → VIP 3.
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.query(Account).filter_by(email="vip_afk@example.com").one()
        a.vip_xp = 2500
        db.commit()
    afk_after = client.get("/afk", headers=_hdr(token)).json()
    assert afk_after["hours_max"] == 16  # VIP 3 perk


def test_daily_drip_idempotent_same_day(client):
    token = _register(client, "vip_drip@example.com")
    # Push to VIP 2 directly.
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.query(Account).filter_by(email="vip_drip@example.com").one()
        a.vip_xp = 600  # > 500 threshold = VIP 2 = 25 daily gems
        db.commit()
    r1 = client.post("/vip/claim", headers=_hdr(token)).json()
    assert r1["granted_gems"] == 25
    r2 = client.post("/vip/claim", headers=_hdr(token)).json()
    assert r2["granted_gems"] == 0
    assert r2["already_claimed"] is True


def test_unranked_account_drip_returns_zero(client):
    token = _register(client, "vip_unranked@example.com")
    r = client.post("/vip/claim", headers=_hdr(token)).json()
    assert r["granted_gems"] == 0


def test_perks_stack_correctly():
    """Pure unit test — VIP 5 perks include all VIP 1-4 perks plus its own."""
    from app.vip import perks_for_level
    p5 = perks_for_level(5)
    assert p5["afk_cap_hours"] == 20
    assert p5["daily_drip_gems"] == 50
    assert p5["auto_battle_speed"] == 3
    assert p5["extra_energy_refresh"] == 1
