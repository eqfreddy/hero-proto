"""End-to-end smoke for hero-proto.

Requires a running server on 127.0.0.1:8000 and the DB seeded (app.seed).
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email() -> str:
    return f"heroproto+{random.randint(100000, 999999)}@example.com"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
        # 1. Register.
        email = _rand_email()
        r = await client.post("/auth/register", json={"email": email, "password": "hunter22"})
        r.raise_for_status()
        token = r.json()["access_token"]
        hdr = {"Authorization": f"Bearer {token}"}
        print(f"registered {email}")

        # 2. /me shows starting resources.
        r = await client.get("/me", headers=hdr)
        r.raise_for_status()
        me = r.json()
        assert me["shards"] >= 10, me
        assert me["energy"] >= 20, me
        print(f"OK me: shards={me['shards']} coins={me['coins']} energy={me['energy']}/{me['energy_cap']}")

        # 3. x10 summon.
        r = await client.post("/summon/x10", headers=hdr)
        r.raise_for_status()
        pulls = r.json()
        assert len(pulls) == 10
        rarity_hist: dict[str, int] = {}
        for p in pulls:
            rarity_hist[p["rarity"]] = rarity_hist.get(p["rarity"], 0) + 1
        print(f"OK x10 summon: {rarity_hist}")

        # 4. Roster populated.
        r = await client.get("/heroes/mine", headers=hdr)
        r.raise_for_status()
        roster = r.json()
        assert len(roster) >= 10
        print(f"OK roster size: {len(roster)}")

        # 5. Stages catalog.
        r = await client.get("/stages")
        r.raise_for_status()
        stages = r.json()
        assert len(stages) >= 5
        stage1 = next(s for s in stages if s["order"] == 1)
        print(f"OK stages: {[s['name'] for s in stages]}")

        # Pick up to 3 highest-power heroes for stage 1.
        rarity_order = {"COMMON": 0, "UNCOMMON": 1, "RARE": 2, "EPIC": 3, "LEGENDARY": 4}
        roster.sort(key=lambda h: (rarity_order.get(h["template"]["rarity"], 0), h["power"]), reverse=True)
        team = [h["id"] for h in roster[:3]]

        # 6. Fight stage 1 — should be winnable even with bad luck.
        r = await client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
        r.raise_for_status()
        battle = r.json()
        print(f"OK stage 1 battle: {battle['outcome']} ticks={sum(1 for e in battle['log'] if e['type']=='TURN')}")
        assert battle["outcome"] == "WIN", battle
        assert battle["first_clear"] is True, battle
        assert any(e["type"] == "END" for e in battle["log"]), "log missing END"
        assert any(e["type"] == "TURN" for e in battle["log"]), "log missing TURN events"
        rew = battle["rewards"]
        assert rew["coins"] > 0 and rew["gems"] > 0, rew  # first-clear gem bonus guaranteed
        print(f"  rewards: {rew}")

        # 7. /me reflects rewards.
        r = await client.get("/me", headers=hdr)
        r.raise_for_status()
        me2 = r.json()
        assert me2["coins"] > me["coins"], f"coins didn't increase: {me['coins']} → {me2['coins']}"
        assert me2["gems"] > me["gems"], f"gems didn't increase: {me['gems']} → {me2['gems']}"
        assert "onboarding_day" in me2["stages_cleared"]
        print(f"OK after battle: coins={me2['coins']} gems={me2['gems']} energy={me2['energy']}")

        # 8. Replay same stage — should NOT be a first clear anymore.
        r = await client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
        r.raise_for_status()
        replay = r.json()
        assert replay["first_clear"] is False, replay
        print("OK replay: first_clear=False")

        # 9. Verify GET /battles/{id}.
        r = await client.get(f"/battles/{battle['id']}", headers=hdr)
        r.raise_for_status()
        fetched = r.json()
        assert fetched["id"] == battle["id"]
        assert fetched["outcome"] == battle["outcome"]
        print("OK battle replay fetched")

        # 10. Try a harder stage to exercise multi-wave + special cooldowns.
        if len(stages) >= 2:
            stage2 = next(s for s in stages if s["order"] == 2)
            r = await client.post(
                "/battles", json={"stage_id": stage2["id"], "team": team}, headers=hdr
            )
            r.raise_for_status()
            b2 = r.json()
            print(f"  stage 2: {b2['outcome']} (first_clear={b2['first_clear']})")
            # Outcome can be WIN or LOSS depending on rarity luck; no assertion.

        # 11. Exhaust energy and confirm 409.
        # Drain via repeated stage 1 fights.
        for _ in range(30):
            r = await client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)
            if r.status_code == 409:
                print(f"OK energy exhausted: {r.json().get('detail')}")
                break
        else:
            print("WARN: didn't hit energy cap in 30 fights; starter energy may be too high")

        print("SMOKE HERO OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
