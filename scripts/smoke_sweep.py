"""Sweep smoke: must clear stage first, then sweep returns aggregated rewards."""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"sweep+{random.randint(100000, 999999)}@example.com"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        r = await client.post("/auth/register", json={"email": _rand_email(), "password": "hunter22"})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.post("/summon/x10", headers=hdr)
        r.raise_for_status()
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        roster = sorted(r.json(), key=lambda h: h["power"], reverse=True)
        team = [h["id"] for h in roster[:3]]

        r = await client.get("/stages")
        r.raise_for_status()
        stage1 = next(s for s in r.json() if s["order"] == 1)

        # Negative: sweep before clear should 409.
        r = await client.post(
            f"/battles/sweep/{stage1['id']}",
            json={"team": team, "count": 3},
            headers=hdr,
        )
        assert r.status_code == 409, r.text
        print("OK sweep before clear rejected (409)")

        # Clear it — retry on bad RNG.
        for _ in range(6):
            r = await client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
            if r.status_code == 409:
                break  # out of energy — give up and fail the next step
            r.raise_for_status()
            if r.json()["outcome"] == "WIN":
                break
        assert r.json()["outcome"] == "WIN", f"couldn't clear stage 1: {r.text}"

        # Now sweep 3x.
        r = await client.get("/me", headers=hdr)
        before = r.json()
        r = await client.post(
            f"/battles/sweep/{stage1['id']}",
            json={"team": team, "count": 3},
            headers=hdr,
        )
        assert r.status_code == 201, r.text
        sw = r.json()
        assert sw["count"] == 3
        assert sw["wins"] + sw["losses"] == 3
        assert sw["energy_spent"] == stage1["energy_cost"] * 3
        print(
            f"OK sweep x3: wins={sw['wins']} losses={sw['losses']} "
            f"energy_spent={sw['energy_spent']} "
            f"rewards={sw['rewards_total']} gear={sw['gear_ids']}"
        )

        r = await client.get("/me", headers=hdr)
        after = r.json()
        assert after["coins"] >= before["coins"], (before["coins"], after["coins"])
        assert after["energy"] < before["energy"]
        print(
            f"OK currencies after: coins {before['coins']}->{after['coins']} "
            f"energy {before['energy']}->{after['energy']}"
        )

        # Count cap: request 20 should 422 (Pydantic validation).
        r = await client.post(
            f"/battles/sweep/{stage1['id']}",
            json={"team": team, "count": 20},
            headers=hdr,
        )
        assert r.status_code == 422, r.text
        print("OK count>10 rejected (422)")

        print("SMOKE SWEEP OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
