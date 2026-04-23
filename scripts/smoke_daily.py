"""Daily quests smoke: roll, progression via summon/battle, claim rewards."""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"daily+{random.randint(100000, 999999)}@example.com"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
        r = await client.post("/auth/register", json={"email": _rand_email(), "password": "hunter22"})
        r.raise_for_status()
        token = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {token}"}

        # 1. /daily lazily rolls 3 quests on first call.
        r = await client.get("/daily", headers=hdr)
        r.raise_for_status()
        quests = r.json()
        assert len(quests) == 3, f"expected 3 dailies, got {len(quests)}"
        today_key = quests[0]["day_key"]
        assert all(q["day_key"] == today_key for q in quests)
        assert all(q["status"] == "ACTIVE" and q["progress"] == 0 for q in quests)
        print(f"OK rolled 3 dailies for {today_key}: {[q['kind'] for q in quests]}")

        # 2. Second call returns the same 3 (idempotent).
        r = await client.get("/daily", headers=hdr)
        r.raise_for_status()
        again = r.json()
        assert [q["id"] for q in again] == [q["id"] for q in quests], "daily set changed on re-read"
        print("OK /daily is idempotent within a day")

        # 3. Summon 10 to progress any SUMMON_HEROES quest.
        r = await client.post("/summon/x10", headers=hdr)
        r.raise_for_status()

        r = await client.get("/daily", headers=hdr)
        r.raise_for_status()
        after_summon = r.json()
        summon_q = next((q for q in after_summon if q["kind"] == "SUMMON_HEROES"), None)
        if summon_q is not None:
            assert summon_q["progress"] >= 1, summon_q
            print(f"OK SUMMON progress: {summon_q['progress']}/{summon_q['goal']}")

        # 4. Win a few stage-1 battles to progress WIN / CLEAR_STAGE_X.
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        roster = sorted(r.json(), key=lambda h: h["power"], reverse=True)
        team = [h["id"] for h in roster[:3]]
        r = await client.get("/stages")
        r.raise_for_status()
        stage1_id = next(s["id"] for s in r.json() if s["order"] == 1)

        for _ in range(5):
            r = await client.post("/battles", json={"stage_id": stage1_id, "team": team}, headers=hdr)
            if r.status_code == 409:
                break

        r = await client.get("/daily", headers=hdr)
        r.raise_for_status()
        after_battles = r.json()
        progressed = [q for q in after_battles if q["progress"] > 0]
        assert progressed, f"no daily progressed after summon + battles: {after_battles}"
        print(f"OK {len(progressed)} quest(s) progressed: {[(q['kind'], f'{q['progress']}/{q['goal']}') for q in progressed]}")

        # 5. Claim any COMPLETE quest (if any exist by now).
        complete = [q for q in after_battles if q["status"] == "COMPLETE"]
        if complete:
            q = complete[0]
            r = await client.get("/me", headers=hdr)
            coins_before = r.json()["coins"]
            r = await client.post(f"/daily/{q['id']}/claim", headers=hdr)
            r.raise_for_status()
            claimed = r.json()
            assert claimed["status"] == "CLAIMED"
            r = await client.get("/me", headers=hdr)
            coins_after = r.json()["coins"]
            assert coins_after >= coins_before, (coins_before, coins_after)
            print(f"OK claimed daily id={q['id']} (kind={q['kind']}); coins {coins_before}->{coins_after}")

            # Second claim should 409.
            r = await client.post(f"/daily/{q['id']}/claim", headers=hdr)
            assert r.status_code == 409
            print("OK double-claim rejected (409)")
        else:
            print("INFO: no daily reached COMPLETE within the test budget; skipping claim assertion")

        print("SMOKE DAILY OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
