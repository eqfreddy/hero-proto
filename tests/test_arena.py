"""Arena: attack flow, match persistence, replay endpoint, auth gating."""

from __future__ import annotations

import json
import random

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, ArenaMatch, DefenseTeam


def _register_and_team(client, prefix: str) -> tuple[dict[str, str], int, list[int]]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    # Summon 10 so there's a team.
    client.post("/summon/x10", headers=hdr)
    roster = sorted(
        client.get("/heroes/mine", headers=hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    team = [h["id"] for h in roster[:3]]
    return hdr, me["id"], team


def _setup_defender_with_defense_team(client) -> tuple[dict[str, str], int, list[int]]:
    hdr, acct_id, team = _register_and_team(client, "defender")
    # Set defense team via the arena router.
    r = client.put("/arena/defense", json={"team": team}, headers=hdr)
    assert r.status_code == 200, r.text
    return hdr, acct_id, team


def test_arena_attack_stores_participants(client) -> None:
    """Each completed arena match now carries participants_json with both teams."""
    _def_hdr, def_id, _def_team = _setup_defender_with_defense_team(client)
    atk_hdr, atk_id, atk_team = _register_and_team(client, "attacker")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201, r.text
    match = r.json()
    parts = match["participants"]
    # 3 attackers + 3 defenders = 6 participants, all with template_code.
    assert len(parts) == 6, f"expected 6 participants, got {len(parts)}: {parts}"
    assert all(p["template_code"] for p in parts), "every participant needs template_code"
    sides = {p["side"] for p in parts}
    assert sides == {"A", "B"}


def test_get_arena_match_returns_full_payload_to_attacker(client) -> None:
    _def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atk2")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    match_id = r.json()["id"]

    r = client.get(f"/arena/matches/{match_id}", headers=atk_hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == match_id
    assert len(body["participants"]) == 6
    assert len(body["log"]) > 0
    # Log has END event at the tail, per combat.py contract.
    assert any(e.get("type") == "END" for e in body["log"])


def test_get_arena_match_allowed_for_defender_too(client) -> None:
    """Defenders can review matches where they were attacked."""
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atk3")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    match_id = r.json()["id"]

    r = client.get(f"/arena/matches/{match_id}", headers=def_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == match_id


def test_get_arena_match_foreign_returns_404(client) -> None:
    """An uninvolved third party gets 404, not 403 — don't leak existence."""
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atk4")
    other_hdr, _, _ = _register_and_team(client, "rando")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    match_id = r.json()["id"]

    r = client.get(f"/arena/matches/{match_id}", headers=other_hdr)
    assert r.status_code == 404


def test_get_arena_match_requires_auth(client) -> None:
    r = client.get("/arena/matches/1")
    assert r.status_code == 401


def test_get_nonexistent_arena_match_is_404(client) -> None:
    hdr, _, _ = _register_and_team(client, "ghost")
    r = client.get("/arena/matches/9999999", headers=hdr)
    assert r.status_code == 404
