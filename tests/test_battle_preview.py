"""Phase 3.2 starter — POST /battles/preview returns expected outcome
distribution + power gap without consuming energy or persisting a row.
"""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"prev+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def test_preview_returns_expected_keys(client) -> None:
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post(
        "/battles/preview",
        json={"stage_id": tutorial["id"], "team": team},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("expected_outcome", "win_probability", "team_power",
              "enemy_power", "power_gap", "sample_ticks",
              "energy_required", "stage_locked", "notes"):
        assert k in body, k
    assert body["expected_outcome"] in ("WIN", "LOSS", "DRAW")
    assert 0.0 <= body["win_probability"] <= 1.0
    assert body["energy_required"] == tutorial["energy_cost"]


def test_preview_does_not_consume_energy(client) -> None:
    hdr, _ = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    energy_before = me_before["energy"]

    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    client.post(
        "/battles/preview",
        json={"stage_id": tutorial["id"], "team": team},
        headers=hdr,
    )
    me_after = client.get("/me", headers=hdr).json()
    # Energy may *replenish* over time (lifespan + worker), but it must
    # never drop on a preview.
    assert me_after["energy"] >= energy_before


def test_preview_does_not_persist_battle_row(client) -> None:
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Account, Battle

    aid = client.get("/me", headers=hdr).json()["id"]
    db = SessionLocal()
    try:
        before = db.scalar(select(Battle).where(Battle.account_id == aid))
    finally:
        db.close()
    assert before is None

    client.post(
        "/battles/preview",
        json={"stage_id": tutorial["id"], "team": team},
        headers=hdr,
    )
    db = SessionLocal()
    try:
        after = db.scalar(select(Battle).where(Battle.account_id == aid))
    finally:
        db.close()
    assert after is None, "preview must not persist a Battle row"


def test_preview_locked_stage_flagged(client) -> None:
    """A HARD stage gated on its NORMAL prerequisite should still preview
    but with stage_locked=true so the UI can render the gate."""
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    locked_hard = next(
        (s for s in stages if s.get("difficulty_tier") == "HARD"
         and s.get("requires_code")),
        None,
    )
    if locked_hard is None:
        import pytest
        pytest.skip("no HARD stage with prerequisite seeded")

    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]
    r = client.post(
        "/battles/preview",
        json={"stage_id": locked_hard["id"], "team": team},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    assert r.json()["stage_locked"] is True
    assert any("locked" in n.lower() for n in r.json()["notes"])


def test_preview_unowned_hero_400s(client) -> None:
    hdr_a, _ = _register(client)
    hdr_b, _ = _register(client)
    heroes_b = client.get("/heroes/mine", headers=hdr_b).json()
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    r = client.post(
        "/battles/preview",
        json={"stage_id": tutorial["id"], "team": [heroes_b[0]["id"]]},
        headers=hdr_a,
    )
    assert r.status_code == 400
