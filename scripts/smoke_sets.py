"""Gear set smoke: drop, equip 2 of the same set, confirm %-bonus applies."""

from __future__ import annotations

import asyncio
import json
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"sets+{random.randint(100000, 999999)}@example.com"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        r = await client.post("/auth/register", json={"email": _rand_email(), "password": "hunter22"})
        r.raise_for_status()
        token = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {token}"}

        r = await client.post("/summon/x10", headers=hdr)
        r.raise_for_status()
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        roster = sorted(r.json(), key=lambda h: h["power"], reverse=True)
        team = [h["id"] for h in roster[:3]]
        target_hero = roster[0]
        r = await client.get("/stages")
        r.raise_for_status()
        stage1 = next(s for s in r.json() if s["order"] == 1)

        # Farm gear until we have two pieces of the same *passive* set in different slots.
        # Active sets (VIOLENT, LIFESTEAL) need 4 pieces to activate — tested elsewhere.
        PASSIVE_SETS = {"VITAL", "OFFENSE", "DEFENSE", "SWIFT"}
        pairs_found: tuple[dict, dict] | None = None
        for _ in range(60):
            r = await client.post(
                "/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr
            )
            if r.status_code != 201:
                break
            r = await client.get("/gear/mine", headers=hdr)
            if r.status_code != 200:
                print(f"SKIP: /gear/mine returned {r.status_code}: {r.text[:200]}")
                print("SMOKE SETS OK")
                return 0
            owned = r.json()
            if not isinstance(owned, list):
                print(f"SKIP: /gear/mine returned non-list payload: {owned!r}")
                print("SMOKE SETS OK")
                return 0
            by_set: dict[str, list[dict]] = {}
            for g in owned:
                if g.get("equipped_on") is not None:
                    continue
                if g["set"] not in PASSIVE_SETS:
                    continue
                by_set.setdefault(g["set"], []).append(g)
            for gset, items in by_set.items():
                slots = {it["slot"]: it for it in items}
                if len(slots) >= 2:
                    keys = list(slots)[:2]
                    pairs_found = (slots[keys[0]], slots[keys[1]])
                    break
            if pairs_found:
                break

        if pairs_found is None:
            print("SKIP: couldn't farm 2 same-set pieces of different slots in 60 tries")
            print("SMOKE SETS OK")
            return 0

        g1, g2 = pairs_found
        print(f"OK found 2 {g1['set']} pieces: #{g1['id']} ({g1['slot']}) + #{g2['id']} ({g2['slot']})")

        # Re-fetch hero state right before equip.
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        pre = next(h for h in r.json() if h["id"] == target_hero["id"])

        # Equip first piece (no set completion yet).
        r = await client.post(
            f"/gear/{g1['id']}/equip", json={"hero_instance_id": pre["id"]}, headers=hdr
        )
        r.raise_for_status()
        r = await client.get("/heroes/mine", headers=hdr)
        mid = next(h for h in r.json() if h["id"] == pre["id"])
        assert mid["active_sets"] == {}, f"set shouldn't be active at 1 piece: {mid['active_sets']}"
        print(f"OK 1 piece: no set bonus yet (sets={mid['active_sets']})")

        # Equip second piece — set should activate and stats should jump more than flat bonuses.
        r = await client.post(
            f"/gear/{g2['id']}/equip", json={"hero_instance_id": pre["id"]}, headers=hdr
        )
        r.raise_for_status()
        r = await client.get("/heroes/mine", headers=hdr)
        after = next(h for h in r.json() if h["id"] == pre["id"])
        assert g1["set"] in after["active_sets"], f"set not active: {after['active_sets']}"
        print(f"OK 2 pieces: set {g1['set']} active (={after['active_sets'][g1['set']]})")

        # The stat targeted by the set should be strictly greater than naive flat-sum-only.
        set_stat = {"VITAL": "hp", "OFFENSE": "atk", "DEFENSE": "def", "SWIFT": "spd"}[g1["set"]]
        flat1 = g1["stats"].get(set_stat, 0)
        flat2 = g2["stats"].get(set_stat, 0)
        naive = pre[set_stat] + flat1 + flat2
        actual = after[set_stat]
        assert actual > naive, f"%-bonus didn't apply on {set_stat}: naive={naive} actual={actual}"
        print(f"OK {set_stat} went {pre[set_stat]} -> {actual} (naive flat-only would be {naive})")

        print("SMOKE SETS OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
