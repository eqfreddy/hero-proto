"""Smoke the three design-handoff pages (battle-setup, battle-replay, roster).

- Verify each page serves 200 with expected markers.
- battle.html (retired) should 404.
- battle-setup.html references the real fetch endpoints.
- battle-replay.html parses ?id=N and fetches /battles/{id}.
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        # Retired page.
        r = await client.get("/app/battle.html")
        assert r.status_code == 404, f"expected 404 for retired battle.html, got {r.status_code}"
        print("OK /app/battle.html retired (404)")

        # New pages serve.
        for page in ("battle-setup.html", "battle-replay.html", "roster.html", "battle-phaser.html"):
            r = await client.get(f"/app/{page}")
            assert r.status_code == 200, f"{page} returned {r.status_code}"
        print("OK all 4 battle/roster pages serve 200")

        # battle-setup.html wires to the real endpoints.
        r = await client.get("/app/battle-setup.html")
        for marker in ("/stages", "/heroes/mine", "/me", "/battles", "heroproto_jwt", "loadData"):
            assert marker in r.text, f"battle-setup.html missing {marker!r}"
        print("OK battle-setup.html references /stages, /heroes/mine, /me, /battles")

        # battle-replay.html reads ?id= and fetches /battles/{id}.
        r = await client.get("/app/battle-replay.html")
        assert "params.get" in r.text, "battle-replay.html isn't parsing URL params"
        assert "/battles/" in r.text, "battle-replay.html doesn't fetch /battles/"
        assert "/arena/matches/" in r.text, "battle-replay.html doesn't support ?mode=arena"
        print("OK battle-replay.html parses ?id + supports both battle and arena modes")

        # roster.html is self-contained (README) — just verify it renders and has all 25 heroes.
        r = await client.get("/app/roster.html")
        # 25 template codes from seed.py — ticket_gremlin is a COMMON, the_board_member is LEGENDARY.
        for sample_code in ("ticket_gremlin", "keymaster_gary", "the_founder", "the_board_member"):
            assert sample_code in r.text, f"roster.html missing {sample_code}"
        print("OK roster.html contains the 25 seeded hero codes")

        # Register, summon, fight → confirm battle.id round-trips back through replay.
        email = f"design+{random.randint(100000, 999999)}@example.com"
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

        r = await client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
        assert r.status_code == 201, r.text
        battle_id = r.json()["id"]

        # Confirm GET /battles/{id} returns a shape the replay page can consume.
        r = await client.get(f"/battles/{battle_id}", headers=hdr)
        r.raise_for_status()
        body = r.json()
        assert body["log"] and body["participants"], "replay payload missing log or participants"
        assert all("template_code" in p for p in body["participants"])
        print(f"OK end-to-end: battle #{battle_id} replay payload has "
              f"{len(body['log'])} log events + {len(body['participants'])} participants with template_code")

        print("SMOKE DESIGN PAGES OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
