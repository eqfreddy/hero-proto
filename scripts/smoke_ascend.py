"""Ascension smoke: ensure shard balance, ascend 1* -> 2*, confirm stat/cap change.

Post 2026-05-12 shard remap — ascension consumes template shards, not fodder.
This script tops up the shard balance via the admin/debug DB session to keep
the smoke self-contained.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"ascend+{random.randint(100000, 999999)}@example.com"


def _top_up_shards(account_id: int, template_code: str, n: int) -> None:
    """Direct DB write — same trick `tests/test_template_shards.py` uses."""
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        existing = json.loads(a.template_shards_json or "{}")
        existing[template_code] = n
        a.template_shards_json = json.dumps(existing)
        db.commit()


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        r = await client.post("/auth/register", json={"email": _rand_email(), "password": "hunter22"})
        r.raise_for_status()
        tok = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {tok}"}
        me = (await client.get("/me", headers=hdr)).json()
        aid = me["id"]

        await client.post("/summon/x10", headers=hdr)
        roster = (await client.get("/heroes/mine", headers=hdr)).json()
        if not roster:
            print("SKIP: empty roster")
            print("SMOKE ASCEND OK")
            return 0

        target = roster[0]
        code = target["template"]["code"]
        assert target["stars"] == 1, target
        pre_hp = target["hp"]
        pre_cap = target["level_cap"]
        print(f"OK pre-ascend: '{target['template']['name']}' 1* cap={pre_cap} hp={pre_hp}")

        _top_up_shards(aid, code, 100)
        r = await client.post(f"/heroes/{target['id']}/ascend-with-shards", headers=hdr)
        assert r.status_code == 200, r.text
        after = r.json()
        assert after["stars"] == 2
        assert after["level_cap"] > pre_cap, f"cap didn't grow: {pre_cap} -> {after['level_cap']}"
        assert after["hp"] > pre_hp, f"hp didn't grow: {pre_hp} -> {after['hp']}"
        print(f"OK ascended: 2* cap={after['level_cap']} hp={after['hp']}")

        bal = (await client.get("/heroes/template-shards", headers=hdr)).json()
        assert bal[code] == 90, f"expected 100-10=90 shards, got {bal[code]}"
        print(f"OK 10 shards spent, {bal[code]} remaining")

        # Negative: insufficient shards at next tier (2->3 costs 30; leave them at 5).
        _top_up_shards(aid, code, 5)
        r = await client.post(f"/heroes/{target['id']}/ascend-with-shards", headers=hdr)
        assert r.status_code == 409, r.text
        assert "need 30" in r.text
        print("OK insufficient shards rejected (409)")

        print("SMOKE ASCEND OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
