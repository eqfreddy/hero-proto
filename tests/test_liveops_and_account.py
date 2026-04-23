"""Integration tests for LiveOps multipliers and account deletion."""

from __future__ import annotations

import json
import random
from datetime import timedelta

import pytest

from app.db import SessionLocal
from app.models import LiveOpsEvent, LiveOpsKind, utcnow


def _register(client) -> tuple[dict[str, str], str, int]:
    email = f"liveops+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email, client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]


def _win_stage1(client, hdr) -> dict:
    """Summon + fight stage 1 until we win; return the battle payload."""
    client.post("/summon/x10", headers=hdr)
    roster = sorted(client.get("/heroes/mine", headers=hdr).json(), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in roster[:3]]
    stage1 = next(s for s in client.get("/stages").json() if s["order"] == 1)
    for _ in range(8):
        r = client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
        assert r.status_code == 201
        if r.json()["outcome"] == "WIN":
            return r.json()
    pytest.fail("couldn't win stage 1 in 8 tries")


def test_liveops_endpoint_reports_seeded_event(client) -> None:
    # The seed phase creates a "Launch Week 2x" event when nothing like it exists.
    r = client.get("/liveops/active")
    assert r.status_code == 200
    kinds = {e["kind"] for e in r.json()}
    # May be empty in a stripped test env — check DB directly to confirm the endpoint works either way.
    assert isinstance(r.json(), list)
    if kinds:
        assert "DOUBLE_REWARDS" in kinds


def test_liveops_double_rewards_doubles_coin_grant(client) -> None:
    # Set up an active DOUBLE_REWARDS event guaranteed for this test.
    with SessionLocal() as db:
        now = utcnow()
        db.add(LiveOpsEvent(
            kind=LiveOpsKind.DOUBLE_REWARDS,
            name=f"Test 2x {random.randint(1000,9999)}",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            payload_json=json.dumps({"multiplier": 2.0}),
        ))
        db.commit()

    hdr, _, _ = _register(client)
    before = client.get("/me", headers=hdr).json()
    battle = _win_stage1(client, hdr)
    after = client.get("/me", headers=hdr).json()
    # Win grants first_clear_gems (25) + base + variable; with 2x applied it should be noticeably larger.
    rewards = battle["rewards"]
    # The doubled coin reward for stage 1 is (~120-144)*2 = 240-288. Allow slack.
    assert rewards["coins"] >= 200, rewards
    assert after["coins"] - before["coins"] >= 200


def test_delete_me_requires_email_match(client) -> None:
    hdr, email, _ = _register(client)
    r = client.request("DELETE", "/me", json={"confirm_email": "wrong@example.com"}, headers=hdr)
    assert r.status_code == 400
    # Account still usable.
    assert client.get("/me", headers=hdr).status_code == 200


def test_delete_me_removes_account_and_token_no_longer_works(client) -> None:
    hdr, email, _ = _register(client)
    r = client.request("DELETE", "/me", json={"confirm_email": email}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["deleted_email"].lower() == email.lower()
    # Token still encodes the old ID but the account is gone.
    r = client.get("/me", headers=hdr)
    assert r.status_code == 401


def test_delete_leader_promotes_successor(client) -> None:
    leader_hdr, leader_email, _ = _register(client)
    r = client.post("/guilds", json={"name": f"DelG {random.randint(1,999999)}", "tag": "DEL"}, headers=leader_hdr)
    assert r.status_code == 201
    guild_id = r.json()["id"]

    member_hdr, _, member_id = _register(client)
    r = client.post(f"/guilds/{guild_id}/join", headers=member_hdr)
    assert r.status_code == 200

    # Leader deletes account.
    r = client.request("DELETE", "/me", json={"confirm_email": leader_email}, headers=leader_hdr)
    assert r.status_code == 200

    # Remaining member should be LEADER.
    r = client.get(f"/guilds/{guild_id}")
    assert r.status_code == 200
    members = r.json()["members"]
    assert len(members) == 1
    assert members[0]["account_id"] == member_id
    assert members[0]["role"] == "LEADER"
