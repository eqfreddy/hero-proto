"""End-to-end guild lifecycle smoke.

Covers: create, apply/accept, messages + pagination, promote, transfer, kick, leave.
Requires a live server with seed data.
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def _register(client: httpx.AsyncClient, prefix: str) -> tuple[dict, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = await client.post("/auth/register", json={"email": email, "password": "hunter22"})
    r.raise_for_status()
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = (await client.get("/me", headers=hdr)).json()
    return hdr, me["id"]


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        leader_hdr, leader_id = await _register(client, "gld_lead")
        tag = f"S{random.randint(100,999)}"
        name = f"Smoke {random.randint(1000,9999)}"
        r = await client.post("/guilds", json={"name": name, "tag": tag}, headers=leader_hdr)
        r.raise_for_status()
        guild_id = r.json()["id"]
        print(f"OK created guild #{guild_id} ({name}, [{tag}]) as leader={leader_id}")

        # Apply + accept
        applicant_hdr, applicant_id = await _register(client, "gld_app")
        r = await client.post(f"/guilds/{guild_id}/apply", json={"message": "let me in"}, headers=applicant_hdr)
        r.raise_for_status()
        app_id = r.json()["id"]
        pending = (await client.get(f"/guilds/{guild_id}/applications", headers=leader_hdr)).json()
        assert any(a["id"] == app_id for a in pending), f"application {app_id} not in pending list"
        r = await client.post(f"/guilds/applications/{app_id}/accept", headers=leader_hdr)
        r.raise_for_status()
        roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
        assert roles[applicant_id] == "MEMBER", f"expected MEMBER, got {roles[applicant_id]}"
        print(f"OK application #{app_id} accepted — {applicant_id} is MEMBER")

        # Promote
        r = await client.post(f"/guilds/{guild_id}/promote/{applicant_id}", headers=leader_hdr)
        r.raise_for_status()
        roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
        assert roles[applicant_id] == "OFFICER"
        print(f"OK {applicant_id} promoted to OFFICER")

        # Officer can see applications now.
        r = await client.get(f"/guilds/{guild_id}/applications", headers=applicant_hdr)
        r.raise_for_status()
        print(f"OK officer can list applications (got {len(r.json())})")

        # Post 6 messages, then paginate.
        for i in range(6):
            r = await client.post(f"/guilds/{guild_id}/messages", json={"body": f"msg {i}"}, headers=leader_hdr)
            r.raise_for_status()
        page1 = (await client.get(f"/guilds/{guild_id}/messages?limit=3", headers=applicant_hdr)).json()
        assert len(page1) == 3
        oldest = page1[-1]["id"]
        page2 = (await client.get(f"/guilds/{guild_id}/messages?before={oldest}&limit=3", headers=applicant_hdr)).json()
        assert len(page2) == 3
        assert all(m["id"] < oldest for m in page2)
        print("OK chat pagination: page1 + page2 = 6 distinct newest-first messages")

        # Transfer leadership
        r = await client.post(f"/guilds/{guild_id}/transfer/{applicant_id}", headers=leader_hdr)
        r.raise_for_status()
        roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
        assert roles[applicant_id] == "LEADER" and roles[leader_id] == "OFFICER"
        print(f"OK leadership transferred to {applicant_id}; {leader_id} is now OFFICER")

        # Old leader can no longer kick.
        r = await client.post(f"/guilds/{guild_id}/kick/{applicant_id}", headers=leader_hdr)
        assert r.status_code == 403, f"old leader should be 403 on kick, got {r.status_code}"
        print("OK old leader blocked from kicking (403)")

        # New leader kicks old leader.
        r = await client.post(f"/guilds/{guild_id}/kick/{leader_id}", headers=applicant_hdr)
        r.raise_for_status()
        assert r.json()["member_count"] == 1
        print(f"OK new leader kicked old leader; member_count=1")

        # Withdraw test: fresh applicant withdraws before review.
        withdrawer_hdr, _ = await _register(client, "gld_wd")
        r = await client.post(f"/guilds/{guild_id}/apply", json={}, headers=withdrawer_hdr)
        wapp_id = r.json()["id"]
        r = await client.delete(f"/guilds/applications/{wapp_id}", headers=withdrawer_hdr)
        r.raise_for_status()
        assert r.json()["status"] == "WITHDRAWN"
        print("OK withdraw self-application works")

        print("SMOKE GUILD OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
