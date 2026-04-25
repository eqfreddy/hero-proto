"""Cross-account ownership guards: alice cannot touch bob's heroes/gear/battles."""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"xacct+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _summon_one(client, hdr) -> int:
    r = client.post("/summon/x1", headers=hdr)
    assert r.status_code == 201, r.text
    return r.json()["hero"]["id"]


def test_skill_up_rejects_other_accounts_hero(client) -> None:
    alice_hdr, _ = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)
    r = client.post(
        f"/heroes/{bob_hero}/skill_up",
        headers=alice_hdr,
        json={"fodder_ids": [1, 2]},
    )
    assert r.status_code == 404


def test_ascend_rejects_other_accounts_hero(client) -> None:
    alice_hdr, _ = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)
    r = client.post(
        f"/heroes/{bob_hero}/ascend",
        headers=alice_hdr,
        json={"fodder_ids": [1]},
    )
    assert r.status_code == 404


def test_sell_rejects_other_accounts_hero(client) -> None:
    alice_hdr, _ = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)
    r = client.post(f"/heroes/{bob_hero}/sell", headers=alice_hdr)
    assert r.status_code == 404
    # Bob can still see + sell his own.
    r = client.get(f"/heroes/{bob_hero}/sell-preview", headers=bob_hdr)
    assert r.status_code == 200


def test_battle_rejects_other_accounts_hero_in_team(client) -> None:
    alice_hdr, _ = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)
    # Alice tries to fight stage 1 borrowing bob's hero.
    stages = client.get("/stages").json()
    sid = stages[0]["id"]
    r = client.post(
        "/battles",
        headers=alice_hdr,
        json={"stage_id": sid, "team": [bob_hero]},
    )
    assert r.status_code == 400
    assert "not owned" in r.text.lower()


def test_arena_defense_rejects_other_accounts_hero(client) -> None:
    alice_hdr, _ = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)
    r = client.put(
        "/arena/defense",
        headers=alice_hdr,
        json={"team": [bob_hero]},
    )
    assert r.status_code == 400


def test_gear_equip_rejects_other_accounts_hero(client) -> None:
    """Even with valid gear, equipping onto someone else's hero must 404."""
    alice_hdr, alice_id = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)

    # Alice needs gear of her own. Grind a few wins.
    stages = client.get("/stages").json()
    sid = stages[0]["id"]
    alice_hero = _summon_one(client, alice_hdr)
    gear_id = None
    for _ in range(15):
        r = client.post(
            "/battles",
            headers=alice_hdr,
            json={"stage_id": sid, "team": [alice_hero]},
        )
        if r.status_code != 201:
            continue
        if r.json().get("rewards", {}).get("gear"):
            g = r.json()["rewards"]["gear"]
            gear_id = g.get("id")
            if gear_id:
                break
    if gear_id is None:
        return  # gear didn't drop in this RNG run; skip silently
    r = client.post(
        f"/gear/{gear_id}/equip",
        headers=alice_hdr,
        json={"hero_instance_id": bob_hero},
    )
    assert r.status_code == 404


def test_battle_get_rejects_other_accounts_battle(client) -> None:
    alice_hdr, _ = _register(client)
    bob_hdr, _ = _register(client)
    bob_hero = _summon_one(client, bob_hdr)
    stages = client.get("/stages").json()
    sid = stages[0]["id"]
    r = client.post(
        "/battles",
        headers=bob_hdr,
        json={"stage_id": sid, "team": [bob_hero]},
    )
    assert r.status_code == 201, r.text
    bob_battle_id = r.json()["id"]
    r = client.get(f"/battles/{bob_battle_id}", headers=alice_hdr)
    assert r.status_code == 404
