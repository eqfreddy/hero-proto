"""Integration tests for guild raids."""

from __future__ import annotations

import random

import pytest

from app.db import SessionLocal
from app.models import Account


def _grant_energy(account_id: int, amount: int) -> None:
    """Tests bypass the energy cap so raid loops don't block on it."""
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        assert a is not None
        a.energy_stored = amount
        db.commit()


def _register_with_team(client, *, extra_energy: int = 0) -> tuple[dict[str, str], int, list[int], str]:
    email = f"raid+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    if extra_energy:
        _grant_energy(me["id"], extra_energy)
    # Summon to get a team.
    client.post("/summon/x10", headers=hdr)
    roster = sorted(client.get("/heroes/mine", headers=hdr).json(), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in roster[:3]]
    return hdr, me["id"], team, email


def _new_guild(client, hdr, tag_prefix: str = "R") -> int:
    r = client.post(
        "/guilds",
        json={"name": f"Raid {random.randint(1,999999)}", "tag": f"{tag_prefix}{random.randint(10,99)}"},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_raid_requires_guild(client) -> None:
    hdr, _, _, _ = _register_with_team(client)
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 20, "duration_hours": 1.0},
        headers=hdr,
    )
    assert r.status_code == 403


def test_full_raid_lifecycle(client) -> None:
    # Grant enough energy to kill a level-1 boss (thick HP pool, ~60-200 attacks).
    leader_hdr, _, team, _ = _register_with_team(client, extra_energy=3000)
    _new_guild(client, leader_hdr)

    # Only LEADER / OFFICER can start — we're leader, good.
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 1, "duration_hours": 1.0},
        headers=leader_hdr,
    )
    assert r.status_code == 201, r.text
    raid = r.json()
    assert raid["remaining_hp"] == raid["max_hp"]
    assert raid["state"] == "ACTIVE"

    # Hammer the boss with many attacks until it falls.
    rid = raid["id"]
    defeated = False
    for _ in range(200):
        r = client.post(f"/raids/{rid}/attack", json={"team": team}, headers=leader_hdr)
        if r.status_code == 409:
            # Out of energy — can't finish; fail the test by timeout instead.
            pytest.fail(f"ran out of energy before boss died: {r.text}")
        assert r.status_code == 201, r.text
        payload = r.json()
        if payload["boss_defeated"]:
            defeated = True
            assert payload["rewards"] is not None
            assert payload["boss_remaining_hp"] == 0
            break
    assert defeated, "boss never died in 200 attacks"

    # Second attack attempt should now 409.
    r = client.post(f"/raids/{rid}/attack", json={"team": team}, headers=leader_hdr)
    assert r.status_code == 409


def test_one_active_raid_per_guild(client) -> None:
    hdr, _, _, _ = _register_with_team(client)
    _new_guild(client, hdr)
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 10, "duration_hours": 1.0},
        headers=hdr,
    )
    assert r.status_code == 201
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 10, "duration_hours": 1.0},
        headers=hdr,
    )
    assert r.status_code == 409
