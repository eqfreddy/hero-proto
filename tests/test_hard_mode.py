"""Hard-mode campaign: tier column on Stage, gating, reward scaling, UI grouping."""

from __future__ import annotations

import random

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Stage, StageDifficulty


def _register(client, prefix: str = "hard") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()
    return {"Authorization": f"Bearer {token}"}, me["id"]


def test_stages_list_exposes_difficulty_tier(client) -> None:
    r = client.get("/stages")
    assert r.status_code == 200
    stages = r.json()
    tiers = {s.get("difficulty_tier") for s in stages}
    assert "NORMAL" in tiers
    assert "HARD" in tiers


def test_hard_stage_has_requires_code_pointing_at_normal(client) -> None:
    r = client.get("/stages").json()
    hard_stages = [s for s in r if s["difficulty_tier"] == "HARD"]
    assert hard_stages, "seed should include at least one HARD stage"
    for hs in hard_stages:
        # Each HARD stage must gate on an existing NORMAL code.
        assert hs["requires_code"], f"HARD stage {hs['code']} has empty requires_code"
        prereq = next((s for s in r if s["code"] == hs["requires_code"]), None)
        assert prereq is not None, f"HARD stage {hs['code']} references missing NORMAL {hs['requires_code']}"
        assert prereq["difficulty_tier"] == "NORMAL"


def test_hard_rewards_scale_up_from_normal(client) -> None:
    r = client.get("/stages").json()
    by_code = {s["code"]: s for s in r}
    # Pick any NORMAL/HARD pair that exists.
    for s in r:
        if s["difficulty_tier"] == "HARD":
            normal = by_code.get(s["requires_code"])
            if normal is None:
                continue
            # 1.5x coins, 2x first-clear gems/shards per our seed.
            assert s["coin_reward"] == int(normal["coin_reward"] * 1.5)
            assert s["first_clear_gems"] == normal["first_clear_gems"] * 2
            assert s["first_clear_shards"] == normal["first_clear_shards"] * 2
            # Energy +1, recommended power 2x.
            assert s["energy_cost"] == normal["energy_cost"] + 1
            assert s["recommended_power"] == normal["recommended_power"] * 2
            return
    raise AssertionError("no NORMAL/HARD pair found in seed to compare")


def test_hard_battle_blocked_without_normal_clear(client) -> None:
    hdr, _ = _register(client)
    # Summon some heroes so we have a valid team.
    client.post("/summon/x10", headers=hdr)
    roster = sorted(
        client.get("/heroes/mine", headers=hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    team = [h["id"] for h in roster[:3]]
    stages = client.get("/stages").json()
    # Pick the H- version of stage 1 (whose NORMAL is cleared of the lowest bar).
    hard_stage1 = next(s for s in stages if s["difficulty_tier"] == "HARD" and s["requires_code"] == "onboarding_day")

    r = client.post("/battles", json={"stage_id": hard_stage1["id"], "team": team}, headers=hdr)
    assert r.status_code == 409, r.text
    assert "NORMAL first" in r.text or "locked" in r.text.lower()


def test_hard_battle_works_after_normal_clear(client) -> None:
    """Smoke: clear NORMAL stage 1 by manually marking it cleared, then run HARD. Must not 409."""
    from app.economy import load_cleared, save_cleared
    from app.models import Account

    hdr, account_id = _register(client)
    client.post("/summon/x10", headers=hdr)
    roster = sorted(
        client.get("/heroes/mine", headers=hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    team = [h["id"] for h in roster[:3]]

    # Flip the prerequisite in-place so the test doesn't depend on RNG-winning stage 1.
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        cleared = load_cleared(a)
        cleared.add("onboarding_day")
        save_cleared(a, cleared)
        db.commit()

    stages = client.get("/stages").json()
    hard_stage1 = next(s for s in stages if s["difficulty_tier"] == "HARD" and s["requires_code"] == "onboarding_day")

    r = client.post("/battles", json={"stage_id": hard_stage1["id"], "team": team}, headers=hdr)
    # Outcome may be WIN or LOSS depending on gear, but must not be gated.
    assert r.status_code == 201, r.text
    assert r.json()["outcome"] in ("WIN", "LOSS", "DRAW")


def test_stages_partial_groups_by_tier(client) -> None:
    """HTMX stages partial renders separate Normal and Hard sections with the expected markers."""
    hdr, _ = _register(client)
    r = client.get("/app/partials/stages", headers=hdr)
    assert r.status_code == 200, r.text[:200]
    body = r.text
    # Section headers by tier.
    assert ">Normal<" in body, "missing Normal tier header"
    assert ">Hard<" in body, "missing Hard tier header"
    # Hard stages render with lock indicator (since the fresh account hasn't cleared anything).
    assert "🔒" in body or "lock" in body.lower(), "expected lock indicator on hard stages"
