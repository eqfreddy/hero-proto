"""Smoke test for the battle replay flow.

Registers, summons, wins a battle, fetches GET /battles/{id}, asserts the
payload has participants + log, and confirms /app/battle.html is served.
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        email = f"bview+{random.randint(100000, 999999)}@example.com"
        r = await client.post("/auth/register", json={"email": email, "password": "hunter22"})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}

        await client.post("/summon/x10", headers=hdr)
        roster = sorted(
            (await client.get("/heroes/mine", headers=hdr)).json(),
            key=lambda h: h["power"], reverse=True,
        )
        team = [h["id"] for h in roster[:3]]
        stage1 = next(s for s in (await client.get("/stages")).json() if s["order"] == 1)

        battle_id = None
        for _ in range(12):
            r = await client.post(
                "/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr,
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert "participants" in body, f"POST /battles missing participants: {body.keys()}"
            assert len(body["participants"]) >= 2, f"expected >=2 participants, got {body['participants']}"
            for p in body["participants"]:
                for field in ("uid", "side", "name", "role", "level", "max_hp"):
                    assert field in p, f"participant missing {field}: {p}"
            if body["outcome"] == "WIN":
                battle_id = body["id"]
                break
        assert battle_id is not None, "couldn't win stage 1 in 12 tries"
        print(f"OK POST /battles returned participants + won stage, id={battle_id}")

        # GET /battles/{id} should return same shape.
        r = await client.get(f"/battles/{battle_id}", headers=hdr)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["id"] == battle_id
        assert len(payload["participants"]) >= 2
        assert len(payload["log"]) > 0
        print(f"OK GET /battles/{battle_id} replays with {len(payload['log'])} log events, "
              f"{len(payload['participants'])} participants")

        # Other accounts can't fetch it.
        r2 = await client.post("/auth/register", json={"email": f"other+{random.randint(1,9999)}@ex.com", "password": "hunter22"})
        r2.raise_for_status()
        other_hdr = {"Authorization": f"Bearer {r2.json()['access_token']}"}
        r = await client.get(f"/battles/{battle_id}", headers=other_hdr)
        assert r.status_code == 404, f"expected 404 for foreign battle, got {r.status_code}"
        print("OK other accounts get 404 on foreign battle")

        # Static page served.
        r = await client.get("/app/battle.html")
        assert r.status_code == 200
        assert "battle replay" in r.text.lower(), "battle.html missing expected content"
        assert "loadBattle" in r.text, "battle.html missing JS"
        print("OK /app/battle.html served")

        print("SMOKE BATTLE VIEW OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
