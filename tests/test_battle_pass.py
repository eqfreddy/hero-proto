"""Tests for the Battle Pass system."""
from __future__ import annotations

import json

import pytest

from tests.conftest import *  # noqa


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_returns_active_season_and_zero_progress(client):
    token = _register(client, "bp_get@example.com")
    r = client.get("/battle-pass", headers=_hdr(token))
    assert r.status_code == 200
    data = r.json()
    assert data["active"] is True
    assert data["season"]["code"] == "season_1_boot_sector"
    assert data["season"]["max_tier"] == 50
    assert data["progress"]["xp_total"] == 0
    assert data["progress"]["current_tier"] == 0
    assert data["progress"]["premium_purchased"] is False
    assert data["progress"]["claimed_free"] == []
    # Tracks have all 50 tiers represented at least once on each side
    free_tiers = {r["tier"] for r in data["season"]["tracks"]["free"]}
    premium_tiers = {r["tier"] for r in data["season"]["tracks"]["premium"]}
    assert free_tiers == set(range(1, 51))
    assert premium_tiers == set(range(1, 51))


def test_battle_grants_xp_via_quest_service_fanout(client):
    token = _register(client, "bp_xp@example.com")
    # Run a real battle so quest_service.record_event fires (and BP fan-out).
    client.post("/summon/x10", headers=_hdr(token))
    heroes = sorted(client.get("/heroes/mine", headers=_hdr(token)).json(),
                    key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in heroes[:3]]
    stages = client.get("/stages").json()
    stage1 = next(s for s in stages if s["order"] == 1)
    r = client.post("/battles", json={"stage_id": stage1["id"], "team": team},
                    headers=_hdr(token))
    assert r.status_code == 201
    # BATTLE_WIN (10 xp) + STAGE_CLEARED (25 xp) at minimum if the auto team won.
    bp = client.get("/battle-pass", headers=_hdr(token)).json()
    assert bp["progress"]["xp_total"] > 0


def test_cannot_claim_locked_tier(client):
    token = _register(client, "bp_locked@example.com")
    r = client.post("/battle-pass/claim/5", json={"track": "free"}, headers=_hdr(token))
    assert r.status_code == 400
    assert "not unlocked" in r.json()["detail"]


def test_cannot_claim_premium_without_purchase(client):
    token = _register(client, "bp_no_premium@example.com")
    # Manually push xp so tier 1 unlocks via direct service call.
    from app.db import SessionLocal
    from app.battle_pass import record_event
    from app.models import Account
    with SessionLocal() as db:
        acct = db.query(Account).filter_by(email="bp_no_premium@example.com").one()
        for _ in range(40):  # 40 wins * 10 xp = 400 xp = tier 2
            record_event(db, acct, "BATTLE_WIN")
        db.commit()
    r = client.post("/battle-pass/claim/1", json={"track": "premium"}, headers=_hdr(token))
    assert r.status_code == 400
    assert "premium" in r.json()["detail"].lower()


def test_claim_free_tier_grants_rewards_and_is_idempotent(client):
    token = _register(client, "bp_free@example.com")
    from app.db import SessionLocal
    from app.battle_pass import record_event
    from app.models import Account
    with SessionLocal() as db:
        acct = db.query(Account).filter_by(email="bp_free@example.com").one()
        for _ in range(25):  # 250 xp -> tier 1
            record_event(db, acct, "BATTLE_WIN")
        db.commit()
    me_before = client.get("/me", headers=_hdr(token)).json()
    r = client.post("/battle-pass/claim/1", json={"track": "free"}, headers=_hdr(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_claimed"] is False
    assert body["granted"].get("coins", 0) == 200
    me_after = client.get("/me", headers=_hdr(token)).json()
    assert me_after["coins"] == me_before["coins"] + 200
    # Re-claim is a no-op
    r2 = client.post("/battle-pass/claim/1", json={"track": "free"}, headers=_hdr(token))
    assert r2.status_code == 200
    assert r2.json()["already_claimed"] is True
    assert r2.json()["granted"] == {}


def test_purchase_premium_unlocks_premium_track(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.mock_payments_enabled", True)
    token = _register(client, "bp_buy@example.com")
    r = client.post("/battle-pass/purchase-premium", headers=_hdr(token))
    assert r.status_code == 201, r.text
    assert r.json()["purchased"] is True
    bp = client.get("/battle-pass", headers=_hdr(token)).json()
    assert bp["progress"]["premium_purchased"] is True
    # And the audit row shows up in /shop/purchases/mine
    purchases = client.get("/shop/purchases/mine", headers=_hdr(token)).json()
    assert any(p["sku"].startswith("battle_pass_premium_") for p in purchases)
