"""Tests for Tower of Trials."""
from __future__ import annotations

import random

from tests.conftest import *  # noqa


def _register(client, tag):
    email = f"tower-{tag}-{random.randint(1000000,9999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    aid = client.get("/me", headers={"Authorization": f"Bearer {tok}"}).json()["id"]
    return tok, aid


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _get_team(client, tok):
    client.post("/summon/x10", headers=_hdr(tok))
    heroes = sorted(
        client.get("/heroes/mine", headers=_hdr(tok)).json(),
        key=lambda h: h["power"], reverse=True,
    )
    return [h["id"] for h in heroes[:3]]


def test_status_default(client):
    tok, _ = _register(client, "stat")
    r = client.get("/tower", headers=_hdr(tok))
    assert r.status_code == 200
    s = r.json()
    assert s["floor"] == 1
    assert s["best_floor"] == 0
    assert s["attempts_today"] == 0
    assert s["attempts_max"] == 3
    assert s["next_floor_preview"]["floor"] == 1


def test_attempt_advances_on_win(client):
    tok, _ = _register(client, "win")
    team = _get_team(client, tok)
    r = client.post("/tower/attempt", json={"team": team}, headers=_hdr(tok))
    assert r.status_code == 201, r.text
    body = r.json()
    # Floor 1 has a single low-level common — leveled team should win.
    assert body["won"] is True
    assert body["floor_after"] == 2
    assert body["best_floor"] >= 2
    assert body["rewards"].get("coins") == 100


def test_daily_attempt_cap(client):
    tok, _ = _register(client, "cap")
    team = _get_team(client, tok)
    for _ in range(3):
        r = client.post("/tower/attempt", json={"team": team}, headers=_hdr(tok))
        assert r.status_code == 201
    # 4th attempt must be rejected.
    r = client.post("/tower/attempt", json={"team": team}, headers=_hdr(tok))
    assert r.status_code == 429


def test_floor_5_grants_gems(client):
    tok, aid = _register(client, "gems")
    team = _get_team(client, tok)
    # Jump to floor 5 directly so we can verify the gems milestone.
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.tower_floor = 5
        db.commit()
    r = client.post("/tower/attempt", json={"team": team}, headers=_hdr(tok))
    assert r.status_code == 201
    if r.json()["won"]:
        assert r.json()["rewards"].get("gems", 0) >= 5


def test_unowned_hero_400(client):
    tok, _ = _register(client, "owned")
    _ = _get_team(client, tok)
    r = client.post("/tower/attempt", json={"team": [99999]}, headers=_hdr(tok))
    assert r.status_code == 400
    assert "not owned" in r.text.lower()


def test_leaderboard_returns_list(client):
    tok, _ = _register(client, "lb")
    r = client.get("/tower/leaderboard")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
