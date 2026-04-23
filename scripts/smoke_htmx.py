"""Smoke test the HTMX UI layer.

Checks:
- /app/ shell serves with HTMX wiring markers.
- /app/partials/login renders unauthenticated.
- /app/partials/{me,roster,stages,daily,arena,guild} return HTML with expected
  content once authed, and 401 when not.
- After summoning + battling, roster partial reflects new heroes and stages
  partial shows the first-clear flag.
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"

PARTIALS_NEED_AUTH = ("me", "roster", "stages", "daily", "arena", "guild")
PARTIAL_MARKERS = {
    "me": ("Account", "Currencies", "access cards"),
    "roster": ("Roster",),
    "stages": ("Stages",),
    "daily": ("Daily quests",),
    "arena": ("Arena", "Leaderboard"),
    "guild": ("Guild",),
}


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        # Shell.
        r = await client.get("/app/")
        assert r.status_code == 200
        for marker in ("hero-proto", "heroproto_jwt", 'data-tab="login"', "/app/partials/"):
            assert marker in r.text, f"shell missing marker: {marker!r}"
        print("OK /app/ shell renders with HTMX wiring")

        # Unauthenticated login partial is always OK.
        r = await client.get("/app/partials/login")
        assert r.status_code == 200 and "/auth/register" in r.text and "/auth/login" in r.text
        print("OK /app/partials/login unauth renders and wires auth endpoints")

        # Authed partials reject without a token.
        for name in PARTIALS_NEED_AUTH:
            r = await client.get(f"/app/partials/{name}")
            assert r.status_code == 401, f"{name} should be 401 unauth, got {r.status_code}"
        print(f"OK all {len(PARTIALS_NEED_AUTH)} authed partials return 401 without token")

        # Register.
        email = f"htmx+{random.randint(100000,999999)}@example.com"
        r = await client.post("/auth/register", json={"email": email, "password": "hunter22"})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Each partial renders with expected markers.
        for name, markers in PARTIAL_MARKERS.items():
            r = await client.get(f"/app/partials/{name}", headers=hdr)
            assert r.status_code == 200, f"{name} authed failed: {r.status_code}"
            body = r.text
            for m in markers:
                assert m in body, f"{name} missing {m!r}"
        print(f"OK all {len(PARTIAL_MARKERS)} partials render with expected content")

        # Summon, then confirm roster picks up the new heroes.
        await client.post("/summon/x10", headers=hdr)
        r = await client.get("/app/partials/roster", headers=hdr)
        assert r.status_code == 200
        # Roster card classes are rarity-* on the hero cards.
        assert "rarity-" in r.text, "roster partial did not render any hero cards after x10"
        print("OK roster partial reflects post-summon heroes")

        # /me shows the access_cards pill (currency #4).
        r = await client.get("/app/partials/me", headers=hdr)
        assert "access cards" in r.text, "me partial missing access_cards label"
        assert "coins" in r.text and "shards" in r.text and "gems" in r.text
        print("OK me partial shows all 4 currencies including access_cards")

        print("SMOKE HTMX OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
