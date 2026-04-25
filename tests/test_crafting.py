"""Crafting — material drops, recipe craftability, atomic craft."""

from __future__ import annotations

import random

from app.crafting import (
    MATERIALS,
    RECIPES,
    grant_material,
    roll_battle_drops,
    roll_raid_drops,
)
from app.db import SessionLocal
from app.models import Account


def _register(client) -> dict[str, str]:
    email = f"craft+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_materials_endpoint_returns_full_catalog(client) -> None:
    hdr = _register(client)
    r = client.get("/crafting/materials", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == len(MATERIALS)
    assert all(m["quantity"] == 0 for m in body)
    codes = {m["code"] for m in body}
    assert codes == set(MATERIALS.keys())


def test_recipes_endpoint_marks_locked_for_fresh_account(client) -> None:
    hdr = _register(client)
    r = client.get("/crafting/recipes", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == len(RECIPES)
    # Fresh account has no materials; nothing is craftable.
    assert all(not r["craftable"] for r in body)
    assert all(r["blocking_reason"] for r in body)


def test_battle_drops_within_expected_table(monkeypatch) -> None:
    """roll_battle_drops should never return a code that's not in MATERIALS."""
    rng = random.Random(42)
    seen: set[str] = set()
    for order in (1, 5, 10, 15):
        for _ in range(200):
            for code, qty in roll_battle_drops(rng, order):
                assert code in MATERIALS
                assert qty >= 1
                seen.add(code)
    # We exercised 4 stage tiers × 200 rolls — at least one drop should fire.
    assert seen, "no material drops fired across 800 rolls — drop tables probably broken"


def test_raid_drops_within_table() -> None:
    rng = random.Random(7)
    fired = False
    for _ in range(500):
        for code, qty in roll_raid_drops(rng):
            assert code in MATERIALS
            assert qty >= 1
            fired = True
    assert fired


def test_craft_blocks_when_missing_materials(client) -> None:
    hdr = _register(client)
    r = client.post("/crafting/convert_keys_to_shards/craft", json={"multiplier": 1}, headers=hdr)
    assert r.status_code == 409
    assert "rusted_keyboard_key" in r.json()["detail"]


def test_craft_unknown_recipe_404(client) -> None:
    hdr = _register(client)
    r = client.post("/crafting/does_not_exist/craft", json={"multiplier": 1}, headers=hdr)
    assert r.status_code == 404


def test_craft_happy_path(client) -> None:
    hdr = _register(client)
    me = client.get("/me", headers=hdr).json()
    # Hand-grant materials + coins so the recipe goes through.
    with SessionLocal() as db:
        acct = db.get(Account, me["id"])
        grant_material(db, acct, "rusted_keyboard_key", 5)
        acct.coins = 500
        db.commit()
        shards_before = acct.shards

    r = client.post("/crafting/convert_keys_to_shards/craft", json={"multiplier": 1}, headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["spent"] == {"rusted_keyboard_key": 5, "coins": 200}
    assert body["granted"]["shards"] == 10
    assert body["materials_after"]["rusted_keyboard_key"] == 0

    me = client.get("/me", headers=hdr).json()
    assert me["shards"] == shards_before + 10


def test_craft_multiplier_atomic(client) -> None:
    hdr = _register(client)
    me = client.get("/me", headers=hdr).json()
    with SessionLocal() as db:
        acct = db.get(Account, me["id"])
        grant_material(db, acct, "rusted_keyboard_key", 15)
        acct.coins = 1000
        db.commit()

    r = client.post("/crafting/convert_keys_to_shards/craft", json={"multiplier": 3}, headers=hdr)
    assert r.status_code == 201
    body = r.json()
    assert body["spent"]["rusted_keyboard_key"] == 15
    assert body["spent"]["coins"] == 600
    assert body["granted"]["shards"] == 30
    assert body["materials_after"]["rusted_keyboard_key"] == 0


def test_craft_logs_history(client) -> None:
    hdr = _register(client)
    me = client.get("/me", headers=hdr).json()
    with SessionLocal() as db:
        acct = db.get(Account, me["id"])
        grant_material(db, acct, "expired_certificate", 6)
        db.commit()

    client.post("/crafting/renew_certificates/craft", json={"multiplier": 2}, headers=hdr)

    r = client.get("/crafting/log", headers=hdr)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["recipe_code"] == "renew_certificates"
    assert rows[0]["inputs"]["expired_certificate"] == 6
    assert "60 gems" in rows[0]["output_summary"]


def test_battle_win_grants_materials(client) -> None:
    """End-to-end: win a tutorial battle, see materials in inventory."""
    hdr = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    roster = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(roster, key=lambda h: h["power"], reverse=True)[:3]]

    won = False
    for _ in range(3):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        if r.json()["outcome"] == "WIN":
            won = True
            break
    assert won

    # Tutorial = order 0, no drops in that tier. Battle stage 1 to actually
    # roll. Need to clear tutorial first to unlock stage 1 (already done).
    stage1 = next(s for s in stages if s["order"] == 1)
    # Try a few times; battle drops are RNG-gated.
    for _ in range(10):
        client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)

    mats = client.get("/crafting/materials", headers=hdr).json()
    total_held = sum(m["quantity"] for m in mats)
    # 10 wins × ~40% drop chance for keyboard keys → ~4 expected; allow slack.
    assert total_held > 0, f"expected at least one material drop in 10 wins, got {total_held}"
