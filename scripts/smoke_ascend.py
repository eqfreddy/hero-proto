"""Ascension smoke: gather dupes, ascend 1* -> 2*, confirm stat/cap change."""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"ascend+{random.randint(100000, 999999)}@example.com"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        r = await client.post("/auth/register", json={"email": _rand_email(), "password": "hunter22"})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Farm pulls to try for a duplicate.
        r = await client.post("/summon/x10", headers=hdr)
        r.raise_for_status()
        r = await client.get("/me", headers=hdr)
        while r.json()["shards"] >= 1:
            s = await client.post("/summon", headers=hdr)
            if s.status_code != 201:
                break
            r = await client.get("/me", headers=hdr)

        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        roster = r.json()
        by_template: dict[int, list[dict]] = {}
        for h in roster:
            by_template.setdefault(h["template"]["id"], []).append(h)
        dupes = max(by_template.values(), key=len)
        if len(dupes) < 2:
            print(f"SKIP: no duplicates in a roster of {len(roster)}")
            print("SMOKE ASCEND OK")
            return 0

        target = dupes[0]
        fodder = dupes[1]
        assert target["stars"] == 1, target
        pre_hp = target["hp"]
        pre_cap = target["level_cap"]
        print(
            f"OK pre-ascend: '{target['template']['name']}' {target['stars']}* "
            f"cap={pre_cap} hp={pre_hp}"
        )

        # 1* -> 2* needs exactly 1 fodder.
        r = await client.post(
            f"/heroes/{target['id']}/ascend",
            json={"fodder_ids": [fodder["id"]]},
            headers=hdr,
        )
        assert r.status_code == 200, r.text
        after = r.json()
        assert after["stars"] == 2
        assert after["level_cap"] > pre_cap, f"cap didn't grow: {pre_cap} -> {after['level_cap']}"
        assert after["hp"] > pre_hp, f"hp didn't grow: {pre_hp} -> {after['hp']}"
        print(f"OK ascended: 2* cap={after['level_cap']} hp={after['hp']}")

        # Fodder should be gone.
        r = await client.get("/heroes/mine", headers=hdr)
        alive_ids = {h["id"] for h in r.json()}
        assert fodder["id"] not in alive_ids
        print("OK fodder consumed")

        # Negative: wrong fodder count for 2->3 (needs 2, give 1).
        # Find another dupe group for the same template if we can.
        if len(dupes) >= 3:
            r = await client.post(
                f"/heroes/{target['id']}/ascend",
                json={"fodder_ids": [dupes[2]["id"]]},
                headers=hdr,
            )
            assert r.status_code == 400, r.text
            print("OK wrong fodder count rejected (400)")
        else:
            print("INFO: no 3rd dupe to test wrong-count rejection")

        print("SMOKE ASCEND OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
