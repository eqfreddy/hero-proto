"""Headless smoke for the hero CLI client.

Drives the Client helper class (no interactive prompts). Requires server running.

Run as a module so the `scripts` package import resolves:
    uv run python -m scripts.smoke_cli
"""

from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

# Allow `python scripts/smoke_cli.py` as well as `python -m scripts.smoke_cli`:
# when invoked directly, the repo root isn't on sys.path, so add it.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import play_hero  # noqa: E402


async def main() -> int:
    cli = play_hero.Client("http://127.0.0.1:8000")
    try:
        email = f"clismoke+{random.randint(100000, 999999)}@example.com"
        await cli.register_or_login(email, "hunter22")

        me = await cli.get("/me")
        assert me["email"] == email
        print(f"OK login: {email} id={me['id']}")

        # Summon x10 via the helper.
        r = await cli.post("/summon/x10")
        assert r.status_code == 201, r.text
        print(f"OK x10 summon ({len(r.json())} heroes)")

        # Roster, sorted by power as in the CLI.
        roster = await cli.get("/heroes/mine")
        assert roster, "roster empty"
        roster.sort(key=lambda h: h["power"], reverse=True)

        # Campaign stage 1. RNG may make this a LOSS with a weak roster — just
        # assert the API responded with a valid outcome.
        stages = await cli.get("/stages")
        stage1_id = next(s["id"] for s in stages if s["order"] == 1)
        r = await cli.post("/battles", {"stage_id": stage1_id, "team": [h["id"] for h in roster[:3]]})
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["outcome"] in ("WIN", "LOSS", "DRAW"), b
        print(f"OK battle via CLI helper: {b['outcome']}")

        # Daily quest list.
        daily = await cli.get("/daily")
        assert len(daily) == 3
        print(f"OK daily quests visible: {[q['kind'] for q in daily]}")

        # Set defense (so we're part of the opponent pool for future tests).
        r = await cli.put("/arena/defense", {"team": [h["id"] for h in roster[:3]]})
        assert r.status_code == 200, r.text
        print("OK defense set via CLI helper")

        print("SMOKE CLI (hero) OK")
        return 0
    finally:
        await cli.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
