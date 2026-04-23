"""Arena smoke: defense set, opponents, attack, rating change, leaderboard."""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def _rand_email(tag: str) -> str:
    return f"arena-{tag}+{random.randint(100000, 999999)}@example.com"


async def _register_and_summon(client, tag: str) -> tuple[str, dict, list[int]]:
    r = await client.post("/auth/register", json={"email": _rand_email(tag), "password": "hunter22"})
    r.raise_for_status()
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    r = await client.post("/summon/x10", headers=hdr)
    r.raise_for_status()
    r = await client.get("/heroes/mine", headers=hdr)
    r.raise_for_status()
    roster = sorted(r.json(), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in roster[:3]]
    r = await client.get("/me", headers=hdr)
    r.raise_for_status()
    me = r.json()
    return token, me, team


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
        # Defender: sets a defense team.
        def_token, defender, def_team = await _register_and_summon(client, "def")
        def_hdr = {"Authorization": f"Bearer {def_token}"}
        r = await client.put("/arena/defense", json={"team": def_team}, headers=def_hdr)
        r.raise_for_status()
        print(f"OK defender set defense (power={r.json()['power']})")

        # Attacker: register and summon.
        atk_token, attacker, atk_team = await _register_and_summon(client, "atk")
        atk_hdr = {"Authorization": f"Bearer {atk_token}"}

        # Opponents endpoint returns up to 3 randomly sampled — over a few calls our
        # defender must appear at least once (pool might include other test accounts).
        found = False
        for _ in range(8):
            r = await client.get("/arena/opponents", headers=atk_hdr)
            r.raise_for_status()
            opps = r.json()
            if any(o["account_id"] == defender["id"] for o in opps):
                found = True
                break
        assert found, "never saw defender in opponents across 8 samples"
        print(f"OK opponents listed: {len(opps)} (defender {defender['id']} present)")

        # Self-attack rejected.
        r = await client.post(
            "/arena/attack",
            json={"defender_account_id": attacker["id"], "team": atk_team},
            headers=atk_hdr,
        )
        assert r.status_code == 400, r.text
        print("OK self-attack rejected (400)")

        # Record rating before.
        r = await client.get("/arena/leaderboard")
        r.raise_for_status()
        board_before = {e["account_id"]: e["arena_rating"] for e in r.json()}

        # Fight the defender.
        r = await client.post(
            "/arena/attack",
            json={"defender_account_id": defender["id"], "team": atk_team},
            headers=atk_hdr,
        )
        r.raise_for_status()
        match = r.json()
        assert match["outcome"] in ("WIN", "LOSS", "DRAW"), match
        print(
            f"OK arena match: {match['outcome']} delta={match['rating_delta']} "
            f"atk->{match['attacker_rating_after']} def->{match['defender_rating_after']}"
        )

        # Leaderboard must reflect rating change.
        r = await client.get("/arena/leaderboard")
        r.raise_for_status()
        board_after = {e["account_id"]: e["arena_rating"] for e in r.json()}
        atk_before = board_before.get(attacker["id"], 1000)
        atk_after = board_after.get(attacker["id"], 1000)
        def_before = board_before.get(defender["id"], 1000)
        def_after = board_after.get(defender["id"], 1000)
        assert atk_after != atk_before or def_after != def_before, (
            f"rating unchanged: atk {atk_before}->{atk_after} def {def_before}->{def_after}"
        )
        print(
            f"OK leaderboard updated (atk {atk_before}->{atk_after}, "
            f"def {def_before}->{def_after})"
        )

        # Defender with no defense set: reset that to empty by unsetting is not supported directly,
        # but attacking a NEW account that never set a team should 409.
        new_token, new_acct, _ = await _register_and_summon(client, "noteam")
        r = await client.post(
            "/arena/attack",
            json={"defender_account_id": new_acct["id"], "team": atk_team},
            headers=atk_hdr,
        )
        assert r.status_code == 409, r.text
        print("OK attacking undefended account rejected (409)")

        print("SMOKE ARENA OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
