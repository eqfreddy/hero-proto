"""Gear smoke: drop, list, equip, unequip, stat change reflected on hero."""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"gear+{random.randint(100000, 999999)}@example.com"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
        email = _rand_email()
        r = await client.post("/auth/register", json={"email": email, "password": "hunter22"})
        r.raise_for_status()
        token = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {token}"}

        # Summon a roster + pick a team.
        r = await client.post("/summon/x10", headers=hdr)
        r.raise_for_status()
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        roster = r.json()
        assert len(roster) >= 3
        roster.sort(key=lambda h: h["power"], reverse=True)
        team = [h["id"] for h in roster[:3]]

        r = await client.get("/stages")
        r.raise_for_status()
        stage1 = next(s for s in r.json() if s["order"] == 1)

        # Fight until a gear drop fires. Losses are RNG — skip them, don't fail.
        dropped = None
        for attempt in range(12):
            r = await client.post(
                "/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr
            )
            if r.status_code == 409:
                break  # out of energy
            r.raise_for_status()
            battle = r.json()
            gear = battle["rewards"].get("gear")
            if gear is not None:
                dropped = gear
                print(f"OK gear dropped on attempt {attempt + 1} ({battle['outcome']}): {gear}")
                break
        assert dropped is not None, "no gear dropped in 12 battles"

        # Verify it shows up in /gear/mine.
        r = await client.get("/gear/mine", headers=hdr)
        r.raise_for_status()
        owned = r.json()
        assert any(g["id"] == dropped["id"] for g in owned), owned
        print(f"OK /gear/mine lists {len(owned)} items")

        # Re-fetch current hero state AFTER the battles (XP/level may have changed).
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        pre = next(h for h in r.json() if h["id"] == roster[0]["id"])

        # Equip to that hero and confirm at least one stat changed.
        r = await client.post(
            f"/gear/{dropped['id']}/equip",
            json={"hero_instance_id": pre["id"]},
            headers=hdr,
        )
        r.raise_for_status()
        equipped = r.json()
        assert equipped["equipped_on"] == pre["id"]

        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        post_equip = next(h for h in r.json() if h["id"] == pre["id"])
        assert dropped["id"] in post_equip["equipped_gear_ids"]
        deltas = {
            "hp": post_equip["hp"] - pre["hp"],
            "atk": post_equip["atk"] - pre["atk"],
            "def": post_equip["def"] - pre["def"],
            "spd": post_equip["spd"] - pre["spd"],
        }
        assert any(v > 0 for v in deltas.values()), f"no stat increased: {deltas}"
        print(f"OK equipped, stat deltas: {deltas}")

        # Unequip and confirm deltas go to zero vs the pre-equip snapshot.
        r = await client.post(f"/gear/{dropped['id']}/unequip", headers=hdr)
        r.raise_for_status()
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        after = next(h for h in r.json() if h["id"] == pre["id"])
        assert dropped["id"] not in after["equipped_gear_ids"]
        assert after["hp"] == pre["hp"] and after["atk"] == pre["atk"], (
            f"stats diverged post-unequip: pre={pre} after={after}"
        )
        print("OK unequip reverts stats")

        print("SMOKE GEAR OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
