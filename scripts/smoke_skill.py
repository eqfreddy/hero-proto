"""Skill-up smoke: spend template shards, verify special_level goes up.

Post 2026-05-12 shard remap — skill_up takes no fodder; it consumes
template shards. This script tops up the balance via the DB session.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"skill+{random.randint(100000, 999999)}@example.com"


def _top_up_shards(account_id: int, template_code: str, n: int) -> None:
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        existing = json.loads(a.template_shards_json or "{}")
        existing[template_code] = n
        a.template_shards_json = json.dumps(existing)
        db.commit()


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
        r = await client.post("/auth/register", json={"email": _rand_email(), "password": "hunter22"})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
        aid = (await client.get("/me", headers=hdr)).json()["id"]

        await client.post("/summon/x10", headers=hdr)
        roster = (await client.get("/heroes/mine", headers=hdr)).json()
        if not roster:
            print("SKIP: empty roster")
            print("SMOKE SKILL OK")
            return 0

        target = roster[0]
        code = target["template"]["code"]
        assert target["special_level"] == 1
        print(f"OK starting: '{target['template']['name']}' special_level=1")

        _top_up_shards(aid, code, 100)

        # 1 -> 2 (cost 5).
        r = await client.post(f"/heroes/{target['id']}/skill_up", headers=hdr)
        assert r.status_code == 200, r.text
        assert r.json()["special_level"] == 2
        print("OK special_level 1 -> 2 (spent 5 shards)")

        bal = (await client.get("/heroes/template-shards", headers=hdr)).json()
        assert bal[code] == 95, f"expected 95 shards, got {bal[code]}"

        # Negative: insufficient shards.
        _top_up_shards(aid, code, 2)  # need 15 for 2->3
        r = await client.post(f"/heroes/{target['id']}/skill_up", headers=hdr)
        assert r.status_code == 409, r.text
        assert "need 15" in r.text
        print("OK insufficient shards rejected (409)")

        print("SMOKE SKILL OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
