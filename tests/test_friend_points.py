"""Tests for Friend Points + friend-summon banner."""
from __future__ import annotations

import random
import pytest

from tests.conftest import *  # noqa


def _register(client, tag):
    email = f"fp-{tag}-{random.randint(1000000,9999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return tok, me["id"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _befriend(client, tok_a, b_id, tok_b, a_id):
    r = client.post("/friends/request", json={"account_id": b_id}, headers=_hdr(tok_a))
    assert r.status_code == 201, r.text
    r = client.post(f"/friends/{a_id}/accept", headers=_hdr(tok_b))
    assert r.status_code == 200, r.text


def test_status_default_for_new_account(client):
    tok, _ = _register(client, "stat")
    r = client.get("/friend-points", headers=_hdr(tok))
    assert r.status_code == 200
    s = r.json()
    assert s["balance"] == 0
    assert s["pings_sent_today"] == 0
    assert s["pings_remaining_today"] == 30


def test_ping_grants_fp_to_both_parties(client):
    tok_a, a_id = _register(client, "a")
    tok_b, b_id = _register(client, "b")
    _befriend(client, tok_a, b_id, tok_b, a_id)
    r = client.post(f"/friend-points/ping/{b_id}", headers=_hdr(tok_a))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sent"] is True
    assert body["fp_granted"] == 5
    # B's balance should also be 5.
    bs = client.get("/friend-points", headers=_hdr(tok_b)).json()
    assert bs["balance"] == 5


def test_ping_idempotent_per_day(client):
    tok_a, a_id = _register(client, "a2")
    tok_b, b_id = _register(client, "b2")
    _befriend(client, tok_a, b_id, tok_b, a_id)
    r1 = client.post(f"/friend-points/ping/{b_id}", headers=_hdr(tok_a))
    assert r1.status_code == 201
    r2 = client.post(f"/friend-points/ping/{b_id}", headers=_hdr(tok_a))
    assert r2.status_code == 409
    assert "already pinged" in r2.text.lower()


def test_ping_strangers_rejected(client):
    tok_a, a_id = _register(client, "a3")
    tok_b, b_id = _register(client, "b3")
    # No friendship.
    r = client.post(f"/friend-points/ping/{b_id}", headers=_hdr(tok_a))
    assert r.status_code == 409
    assert "not friends" in r.text.lower()


def test_self_ping_rejected(client):
    tok, aid = _register(client, "self")
    r = client.post(f"/friend-points/ping/{aid}", headers=_hdr(tok))
    assert r.status_code == 409


def test_summon_requires_balance(client):
    tok, _ = _register(client, "broke")
    r = client.post("/friend-points/summon", headers=_hdr(tok))
    assert r.status_code == 409
    assert "friend points" in r.text.lower()


def test_summon_consumes_50_fp_and_grants_hero(client):
    tok, aid = _register(client, "rich")
    # Top up FP directly.
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.friend_points = 60
        db.commit()
    r = client.post("/friend-points/summon", headers=_hdr(tok))
    assert r.status_code == 201, r.text
    body = r.json()
    assert "hero" in body
    assert body["rarity"] in ("COMMON", "UNCOMMON", "RARE", "EPIC")
    s = client.get("/friend-points", headers=_hdr(tok)).json()
    assert s["balance"] == 10  # 60 - 50


def test_fp_pity_does_not_share_with_standard_pity(client):
    """Standard banner pulls_since_epic should not move when player pulls
    on the friend banner."""
    tok, aid = _register(client, "split")
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.friend_points = 1000
        a.pulls_since_epic = 25
        db.commit()
    for _ in range(5):
        client.post("/friend-points/summon", headers=_hdr(tok))
    me = client.get("/me", headers=_hdr(tok)).json()
    # Standard pity unchanged (5 friend pulls don't bump it).
    assert me["pulls_since_epic"] == 25
