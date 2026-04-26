"""Phase 2.4 follow-up — verify QoL unlocks owned via /shop/iap actually
do something at the gameplay layer.

Pre-fix the catalog sold the flags but nothing read them. These tests
pin the wiring:
  - extra_team_presets bumps the preset cap from 5 to 10.
  - auto_battle echoes `auto_resolved: true` on /battles when set.
  - Players without the unlock get the standard cap / watch flow.
"""

from __future__ import annotations

import json
import random


def _register(client) -> tuple[dict, int]:
    email = f"qolwire+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _grant_unlock(aid: int, code: str) -> None:
    """Direct-DB grant of a QoL unlock — bypasses the IAP path so the
    tests don't depend on receipt fixtures."""
    from datetime import datetime, timezone
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        try:
            owned = json.loads(a.qol_unlocks_json or "{}")
        except json.JSONDecodeError:
            owned = {}
        owned[code] = datetime.now(timezone.utc).isoformat()
        a.qol_unlocks_json = json.dumps(owned, separators=(",", ":"))
        db.commit()
    finally:
        db.close()


def _make_preset(client, hdr, name: str) -> int:
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in heroes[:1]]  # 1 hero is enough — server validates ≥1
    r = client.post(
        "/me/team-presets",
        json={"name": name, "team": team},
        headers=hdr,
    )
    return r.status_code


# --- extra_team_presets ----------------------------------------------------


def test_preset_cap_default_is_five(client) -> None:
    hdr, _ = _register(client)
    for i in range(5):
        assert _make_preset(client, hdr, f"slot{i}") == 201
    # 6th slot rejected without the unlock.
    r = _make_preset(client, hdr, "slot5")
    assert r == 409


def test_preset_cap_doubles_with_extra_team_presets_unlock(client) -> None:
    hdr, aid = _register(client)
    _grant_unlock(aid, "extra_team_presets")
    for i in range(10):
        assert _make_preset(client, hdr, f"slot{i}") == 201
    # 11th still rejected.
    r = _make_preset(client, hdr, "slot10")
    assert r == 409


# --- auto_battle ------------------------------------------------------------


def test_battle_auto_flag_no_unlock_runs_watch_flow(client) -> None:
    """Players without the QoL unlock get the regular response — server
    refuses to silently skip the watch step."""
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post(
        "/battles",
        json={"stage_id": tutorial["id"], "team": team, "auto": True},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    assert r.json()["auto_resolved"] is False, r.json()


def test_battle_auto_flag_with_unlock_echoes_auto_resolved(client) -> None:
    hdr, aid = _register(client)
    _grant_unlock(aid, "auto_battle")
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post(
        "/battles",
        json={"stage_id": tutorial["id"], "team": team, "auto": True},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    assert r.json()["auto_resolved"] is True, r.json()


def test_battle_default_auto_resolved_false(client) -> None:
    """Omitting `auto` from the body must not flip auto_resolved on."""
    hdr, aid = _register(client)
    _grant_unlock(aid, "auto_battle")
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post(
        "/battles",
        json={"stage_id": tutorial["id"], "team": team},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    assert r.json()["auto_resolved"] is False, r.json()
