"""Raid smoke: guild creation, raid start, classic attack, interactive attack, leaderboard.

Mirrors `tests/test_raids.py` as a live HTTP walkthrough. Run against a
seeded local server (or `BASE=https://hero-proto.fly.dev python scripts/smoke_raid.py`).
"""

from __future__ import annotations

import asyncio
import os
import random
import sys

import httpx

BASE = os.environ.get("BASE", "http://127.0.0.1:8000")

BOSS_CODE = "raidboss_chaos_dragon"
BOSS_LEVEL = 5  # Keep low so a freshly-summoned roster can dent the boss.


def _rand_email(tag: str) -> str:
    return f"raid-{tag}+{random.randint(100000, 999999)}@example.com"


async def _register(client: httpx.AsyncClient, tag: str) -> tuple[dict, int, list[int]]:
    """Register, run a x10 summon, return (auth header, account id, top-3 team)."""
    r = await client.post("/auth/register", json={"email": _rand_email(tag), "password": "hunter22"})
    r.raise_for_status()
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.post("/summon/x10", headers=hdr)
    r.raise_for_status()
    r = await client.get("/heroes/mine", headers=hdr)
    r.raise_for_status()
    roster = sorted(r.json(), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in roster[:3]]
    r = await client.get("/me", headers=hdr)
    r.raise_for_status()
    return hdr, r.json()["id"], team


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        leader_hdr, leader_id, leader_team = await _register(client, "ldr")
        member_hdr, member_id, member_team = await _register(client, "mbr")

        # Leader creates the guild
        tag = f"R{random.randint(100, 999)}"
        r = await client.post("/guilds", json={"name": f"Raid Smoke {random.randint(1000,9999)}", "tag": tag}, headers=leader_hdr)
        r.raise_for_status()
        guild_id = r.json()["id"]
        print(f"OK guild #{guild_id} ([{tag}]) created")

        # Member applies, leader accepts
        r = await client.post(f"/guilds/{guild_id}/apply", json={"message": "raid plz"}, headers=member_hdr)
        r.raise_for_status()
        app_id = r.json()["id"]
        r = await client.post(f"/guilds/applications/{app_id}/accept", headers=leader_hdr)
        r.raise_for_status()
        print(f"OK member {member_id} joined guild")

        # Start raid (officers/leader only; leader is fine)
        r = await client.post(
            "/raids/start",
            json={"boss_template_code": BOSS_CODE, "boss_level": BOSS_LEVEL, "tier": "T1"},
            headers=leader_hdr,
        )
        r.raise_for_status()
        raid = r.json()
        raid_id = raid["id"]
        starting_hp = raid["remaining_hp"]
        print(f"OK raid #{raid_id} started — boss={BOSS_CODE} hp={starting_hp}")

        # Classic attack from leader
        r = await client.post(f"/raids/{raid_id}/attack", json={"team": leader_team}, headers=leader_hdr)
        r.raise_for_status()
        atk = r.json()
        assert atk["damage_dealt"] >= 0, "negative damage"
        print(f"OK leader classic attack — dmg={atk['damage_dealt']} hp_left={atk['boss_remaining_hp']}")

        # Re-fetch and check contributor list reflects the leader
        r = await client.get(f"/raids/{raid_id}", headers=leader_hdr)
        r.raise_for_status()
        data = r.json()
        contrib_ids = {c["account_id"] for c in data["contributors"]}
        assert leader_id in contrib_ids, f"leader {leader_id} not in contributors {contrib_ids}"
        print(f"OK leader recorded as contributor")

        # Member can read raid state
        r = await client.get(f"/raids/{raid_id}", headers=member_hdr)
        r.raise_for_status()
        assert r.json()["id"] == raid_id

        # Interactive attack from member (cooldown is per-account, so fresh)
        r = await client.post(
            f"/raids/{raid_id}/attack/interactive/start",
            json={"team": member_team},
            headers=member_hdr,
        )
        if r.status_code == 429:
            print("SKIP interactive — cooldown hit, classic attack burnt the bucket")
        else:
            r.raise_for_status()
            session = r.json()
            session_id = session["session_id"]
            # Drain the auto-loop: just keep posting WAIT until done or 50 ticks.
            for _ in range(50):
                if session.get("done"):
                    break
                r = await client.post(
                    f"/raids/interactive/{session_id}/act",
                    json={"action": "WAIT"},
                    headers=member_hdr,
                )
                r.raise_for_status()
                session = r.json()
            assert session.get("done"), "interactive session never finished"
            print(f"OK member interactive run — done after {session.get('turns', '?')} turns")

        # Leaderboard returns a list
        r = await client.get("/raids/leaderboard?days=7&limit=10")
        r.raise_for_status()
        assert isinstance(r.json(), list)
        print(f"OK leaderboard responded with {len(r.json())} guild rows")

        print("\nALL OK — raid smoke green")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
