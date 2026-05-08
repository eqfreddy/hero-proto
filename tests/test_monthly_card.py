"""Tests for the Monthly Card subscription."""
from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import *  # noqa


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_status_inactive_for_new_account(client):
    token = _register(client, "mc_new@example.com")
    r = client.get("/monthly-card", headers=_hdr(token))
    assert r.status_code == 200
    s = r.json()
    assert s["active"] is False
    assert s["days_remaining"] == 0
    assert s["drip_available_today"] is False


def test_purchase_via_endpoint_grants_card_and_instant_gems(client):
    token = _register(client, "mc_buy@example.com")
    me_before = client.get("/me", headers=_hdr(token)).json()
    r = client.post("/monthly-card/purchase", headers=_hdr(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mode"] == "mock"
    assert body["purchased"] is True
    me_after = client.get("/me", headers=_hdr(token)).json()
    # 100 instant + 50 same-day drip claimed via /me lazy hook = 150
    assert me_after["gems"] == me_before["gems"] + 150
    mc = me_after["monthly_card"]
    assert mc["active"] is True
    assert mc["days_remaining"] in (29, 30)


def test_purchase_via_shop_sku_grants_card(client):
    token = _register(client, "mc_shop@example.com")
    r = client.post("/shop/purchases", json={"sku": "monthly_card"}, headers=_hdr(token))
    assert r.status_code == 201, r.text
    me = client.get("/me", headers=_hdr(token)).json()
    assert me["monthly_card"]["active"] is True


def test_drip_idempotent_same_day(client):
    token = _register(client, "mc_drip@example.com")
    client.post("/monthly-card/purchase", headers=_hdr(token))
    me_after_purchase = client.get("/me", headers=_hdr(token)).json()
    gems = me_after_purchase["gems"]
    # Second /me hit same UTC day should not grant more drip.
    me_again = client.get("/me", headers=_hdr(token)).json()
    assert me_again["gems"] == gems
    # Explicit claim endpoint also a no-op same day.
    claim = client.post("/monthly-card/claim", headers=_hdr(token)).json()
    assert claim["granted_gems"] == 0
    assert claim["already_claimed"] is True


def test_purchase_stacks_extends_end_date(client):
    token = _register(client, "mc_stack@example.com")
    client.post("/monthly-card/purchase", headers=_hdr(token))
    end1 = client.get("/monthly-card", headers=_hdr(token)).json()["ends_at"]
    client.post("/monthly-card/purchase", headers=_hdr(token))
    end2 = client.get("/monthly-card", headers=_hdr(token)).json()["ends_at"]
    assert datetime.fromisoformat(end2) > datetime.fromisoformat(end1)


def test_inactive_card_does_not_drip(client):
    token = _register(client, "mc_inactive@example.com")
    me = client.get("/me", headers=_hdr(token)).json()
    gems_before = me["gems"]
    claim = client.post("/monthly-card/claim", headers=_hdr(token)).json()
    assert claim["granted_gems"] == 0
    me_after = client.get("/me", headers=_hdr(token)).json()
    assert me_after["gems"] == gems_before
