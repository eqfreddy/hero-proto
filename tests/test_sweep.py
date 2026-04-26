"""POST /battles/sweep/{stage_id} — auto-pulls last winning team if
none provided (bug #3 fix). Previously the team was required and the
frontend's `{count: N}`-only call returned 422 with `[object Object]`
in the toast.
"""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"sweep+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _bump_energy(aid: int, n: int) -> None:
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.energy_stored = n
        db.commit()
    finally:
        db.close()


def _clear_tutorial_and_collect(client, hdr) -> int:
    """Win the tutorial stage so it counts as 'cleared' for sweep
    purposes. Returns the tutorial stage_id."""
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]
    # Tutorial is winnable with starter COMMONs but RNG can dip — try a few times.
    for _ in range(4):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        if r.status_code == 201 and r.json()["outcome"] == "WIN":
            return tutorial["id"]
    raise AssertionError("tutorial did not win in 4 tries")


def test_sweep_with_explicit_team(client) -> None:
    hdr, aid = _register(client)
    stage_id = _clear_tutorial_and_collect(client, hdr)
    _bump_energy(aid, 100)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post(
        f"/battles/sweep/{stage_id}",
        json={"team": team, "count": 2},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["count"] == 2
    assert body["wins"] + body["losses"] == 2


def test_sweep_without_team_uses_last_winning_team(client) -> None:
    """Phase 2 fix for bug #3: omitting `team` falls back to the most
    recent winning team for that stage. No more 422."""
    hdr, aid = _register(client)
    stage_id = _clear_tutorial_and_collect(client, hdr)
    _bump_energy(aid, 100)

    r = client.post(
        f"/battles/sweep/{stage_id}",
        json={"count": 2},  # no team — same shape the dashboard sends
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["count"] == 2


def test_sweep_no_team_no_history_400(client) -> None:
    """If we can't find a previous winning team, we should reject with
    400 (a clear 'pass team explicitly' message), not 422 / 500."""
    from app.db import SessionLocal
    from app.models import Battle, BattleOutcome, HeroInstance, Stage

    hdr, aid = _register(client)
    # Force-mark a stage as cleared but never actually win it (so no
    # winning Battle row exists).
    stages = client.get("/stages").json()
    stage = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    import json
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.stages_cleared_json = json.dumps([stage["code"]])
        a.energy_stored = 100
        db.commit()
    finally:
        db.close()

    r = client.post(
        f"/battles/sweep/{stage['id']}",
        json={"count": 1},
        headers=hdr,
    )
    assert r.status_code == 400, r.text
    assert "team" in r.text.lower()


def test_sweep_uncleared_stage_409(client) -> None:
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    stage_id = stages[0]["id"]
    r = client.post(f"/battles/sweep/{stage_id}", json={"count": 1}, headers=hdr)
    assert r.status_code == 409
