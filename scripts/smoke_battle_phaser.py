"""Smoke for the Phaser battle view and placeholder portrait endpoint.

Validates:
- /app/battle-phaser.html renders with expected markup (Phaser CDN, scene class).
- /app/placeholder/hero/<code>.svg serves SVG for both known and unknown template codes.
- /battles/{id} participants now include template_code so the Phaser preloader can work.
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        # Static Phaser page.
        r = await client.get("/app/battle-phaser.html")
        assert r.status_code == 200, r.text[:200]
        for marker in ("Phaser", "BattleScene", "battle-phaser.html" if False else "battle replay",
                       "/battles/", "/app/placeholder/hero/"):
            assert marker in r.text, f"battle-phaser.html missing {marker!r}"
        print("OK /app/battle-phaser.html renders with Phaser bootstrap")

        # Placeholder SVG — known code.
        r = await client.get("/app/placeholder/hero/ticket_gremlin.svg")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/svg")
        assert "<svg" in r.text and "</svg>" in r.text
        print("OK placeholder for known code serves SVG")

        # Placeholder SVG — unknown code (still serves a fallback image, doesn't 404).
        r = await client.get("/app/placeholder/hero/not_a_real_hero.svg")
        assert r.status_code == 200
        assert "<svg" in r.text
        print("OK placeholder for unknown code serves fallback SVG")

        # Register + win a battle so we can verify template_code lands in participants.
        email = f"phaser+{random.randint(100000, 999999)}@example.com"
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

        # Run until we get a WIN, then fetch and check participants.
        bid = None
        for _ in range(10):
            r = await client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
            assert r.status_code == 201
            if r.json()["outcome"] == "WIN":
                bid = r.json()["id"]
                break
        assert bid is not None, "couldn't clear stage 1 in 10 tries"

        r = await client.get(f"/battles/{bid}", headers=hdr)
        r.raise_for_status()
        participants = r.json()["participants"]
        assert all("template_code" in p for p in participants), \
            f"participants missing template_code: {participants}"
        codes = {p["template_code"] for p in participants}
        assert len(codes) > 0 and all(codes)  # no empty strings
        print(f"OK battle #{bid} participants carry template_code: {sorted(codes)}")

        # Every template_code resolves to a placeholder (real art optional).
        for code in codes:
            r = await client.get(f"/app/placeholder/hero/{code}.svg")
            assert r.status_code == 200, f"placeholder failed for {code}"
        print(f"OK placeholders serve for all {len(codes)} template codes in the battle")

        print("SMOKE BATTLE PHASER OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
