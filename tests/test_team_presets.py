"""Phase 1.3: team presets + last-team helper."""

from __future__ import annotations

import random


def _register_with_heroes(client) -> tuple[dict[str, str], list[int]]:
    email = f"preset+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Starter team grants 3 heroes on register; plus a summon for variety.
    client.post("/summon/x10", headers=hdr)
    roster = client.get("/heroes/mine", headers=hdr).json()
    return hdr, [h["id"] for h in roster[:3]]


def test_preset_create_list_delete(client) -> None:
    hdr, team = _register_with_heroes(client)

    # Initially empty.
    r = client.get("/me/team-presets", headers=hdr)
    assert r.status_code == 200 and r.json() == []

    r = client.post("/me/team-presets", json={"name": "main", "team": team}, headers=hdr)
    assert r.status_code == 201
    preset_id = r.json()["id"]
    assert r.json()["name"] == "main"
    assert r.json()["team"] == team

    r = client.get("/me/team-presets", headers=hdr)
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.delete(f"/me/team-presets/{preset_id}", headers=hdr)
    assert r.status_code == 200

    r = client.get("/me/team-presets", headers=hdr)
    assert r.json() == []


def test_preset_upsert_overwrites_same_name(client) -> None:
    hdr, team = _register_with_heroes(client)
    client.post("/me/team-presets", json={"name": "main", "team": team[:2]}, headers=hdr)
    r = client.post("/me/team-presets", json={"name": "main", "team": team}, headers=hdr)
    assert r.status_code == 201, r.text
    assert r.json()["team"] == team

    presets = client.get("/me/team-presets", headers=hdr).json()
    assert len(presets) == 1  # overwrote, didn't append


def test_preset_max_count(client) -> None:
    hdr, team = _register_with_heroes(client)
    for i in range(5):
        r = client.post("/me/team-presets", json={"name": f"p{i}", "team": team}, headers=hdr)
        assert r.status_code == 201
    # 6th fails.
    r = client.post("/me/team-presets", json={"name": "p5", "team": team}, headers=hdr)
    assert r.status_code == 409
    assert "max" in r.json()["detail"].lower()


def test_preset_strips_unowned_heroes(client) -> None:
    hdr, team = _register_with_heroes(client)
    # 2 owned + 1 unowned (fits in 3-slot max).
    mixed = team[:2] + [999999]
    r = client.post("/me/team-presets", json={"name": "main", "team": mixed}, headers=hdr)
    assert r.status_code == 201
    assert r.json()["team"] == team[:2]  # unowned stripped


def test_preset_rejects_empty_after_strip(client) -> None:
    hdr, _ = _register_with_heroes(client)
    r = client.post("/me/team-presets", json={"name": "bogus", "team": [999998, 999999]}, headers=hdr)
    assert r.status_code == 400


def test_last_team_returns_most_recent_battle_team(client) -> None:
    hdr, team = _register_with_heroes(client)
    # No history: empty.
    r = client.get("/me/last-team", headers=hdr)
    assert r.status_code == 200
    assert r.json() == {"team": [], "source": "empty"}

    # Fight stage 1 to seed a Battle row.
    stages = client.get("/stages").json()
    stage1 = next(s for s in stages if s["order"] == 1)
    client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
    r = client.get("/me/last-team", headers=hdr)
    assert r.status_code == 200
    assert r.json()["source"] == "battle"
    assert r.json()["team"] == team
