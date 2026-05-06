"""Tests for the quest progression engine."""
from __future__ import annotations
import json
from tests.conftest import *  # noqa


def _register(client, email="quest@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_new_account_enrolled_in_onboarding(client):
    token = _register(client, "enroll@example.com")
    r = client.get("/quests/active", headers=_headers(token))
    assert r.status_code == 200
    quests = r.json()
    assert len(quests) == 1
    assert quests[0]["quest_id"] == "onboarding_week_one"


def test_battle_complete_advances_quest(client):
    from app.db import SessionLocal
    from app.models import AccountQuest
    token = _register(client, "battle_quest@example.com")
    # Trigger a battle via existing full_loop approach
    r = client.post("/summon/x10", headers=_headers(token))
    assert r.status_code == 201
    heroes = sorted(client.get("/heroes/mine", headers=_headers(token)).json(),
                    key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in heroes[:3]]
    stages = client.get("/stages").json()
    stage1 = next(s for s in stages if s["order"] == 1)
    client.post("/battles", json={"stage_id": stage1["id"], "team": team},
                headers=_headers(token))
    # BATTLE_COMPLETE task should have advanced
    r = client.get("/quests/active", headers=_headers(token))
    quest = r.json()[0]
    task = next(t for t in quest["tasks"] if t["event"] == "BATTLE_COMPLETE")
    assert task["current"] >= 1


def test_quest_not_claimable_until_complete(client):
    token = _register(client, "claim_early@example.com")
    r = client.post("/quests/onboarding_week_one/claim",
                    json={"choice": "gems"}, headers=_headers(token))
    assert r.status_code == 400
    assert "not complete" in r.json()["detail"]


def test_dismiss_hides_quest(client):
    token = _register(client, "dismiss@example.com")
    r = client.post("/quests/onboarding_week_one/dismiss", headers=_headers(token))
    assert r.status_code == 200
    r = client.get("/quests/active", headers=_headers(token))
    assert r.json() == []
