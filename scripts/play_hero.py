"""Menu-driven CLI client for hero-proto.

Usage:
    uv run python scripts/play_hero.py [--server http://127.0.0.1:8000]
                                       [--email X --password Y]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from typing import Any

import httpx


def _rand_email() -> str:
    return f"cli+{random.randint(100000, 999999)}@example.com"


RARITY_ORDER = {"COMMON": 0, "UNCOMMON": 1, "RARE": 2, "EPIC": 3, "LEGENDARY": 4}


class Client:
    def __init__(self, base: str) -> None:
        self.base = base
        self.client = httpx.AsyncClient(base_url=base, timeout=20.0)
        self.token: str | None = None

    async def close(self) -> None:
        await self.client.aclose()

    @property
    def hdr(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def register_or_login(self, email: str, password: str) -> None:
        r = await self.client.post("/auth/login", json={"email": email, "password": password})
        if r.status_code == 401:
            r = await self.client.post("/auth/register", json={"email": email, "password": password})
        r.raise_for_status()
        self.token = r.json()["access_token"]

    async def get(self, path: str) -> Any:
        r = await self.client.get(path, headers=self.hdr)
        r.raise_for_status()
        return r.json()

    async def post(self, path: str, body: dict | None = None) -> httpx.Response:
        return await self.client.post(path, json=body or {}, headers=self.hdr)

    async def put(self, path: str, body: dict) -> httpx.Response:
        return await self.client.put(path, json=body, headers=self.hdr)


def _prompt(msg: str) -> str:
    try:
        return input(msg)
    except (EOFError, KeyboardInterrupt):
        return ""


def _print_header(me: dict) -> None:
    print()
    print("=" * 70)
    print(
        f" {me['email']}  |  gems {me['gems']}  coins {me['coins']}  shards {me['shards']}"
        f"  energy {me['energy']}/{me['energy_cap']}"
    )
    print("=" * 70)


async def _show_roster(cli: Client) -> list[dict]:
    roster = await cli.get("/heroes/mine")
    roster.sort(
        key=lambda h: (RARITY_ORDER.get(h["template"]["rarity"], 0), h["power"]), reverse=True
    )
    print(f"\n Roster ({len(roster)} heroes):")
    for h in roster[:30]:
        t = h["template"]
        eq = f" gear:{len(h['equipped_gear_ids'])}" if h["equipped_gear_ids"] else ""
        print(
            f"  #{h['id']:>4}  {t['rarity']:<9} {t['name']:<22} "
            f"lv{h['level']:<2} sl{h['special_level']}  "
            f"HP {h['hp']:<5} ATK {h['atk']:<4} DEF {h['def']:<4} SPD {h['spd']:<3}  "
            f"pwr {h['power']}{eq}"
        )
    if len(roster) > 30:
        print(f"  ... and {len(roster) - 30} more")
    return roster


async def _do_summon(cli: Client) -> None:
    print("\n 1) x1  2) x10  anything else = cancel")
    pick = _prompt(" > ").strip()
    path = "/summon/x10" if pick == "2" else ("/summon" if pick == "1" else None)
    if path is None:
        return
    r = await cli.post(path)
    if r.status_code != 201:
        print(f" summon failed: {r.status_code} {r.text.strip()}")
        return
    data = r.json()
    pulls = data if isinstance(data, list) else [data]
    for p in pulls:
        print(f"  + {p['rarity']:<9} {p['hero']['template']['name']} (id {p['hero']['id']})")


def _print_battle_log(log: list[dict], verbose: bool = False) -> None:
    turns = sum(1 for e in log if e["type"] == "TURN")
    damage = sum(e["amount"] for e in log if e["type"] == "DAMAGE" and isinstance(e.get("amount"), int))
    deaths = sum(1 for e in log if e["type"] == "DEATH")
    end = next((e for e in log if e["type"] == "END"), None)
    print(f" Turns: {turns}   Total damage: {damage}   Deaths: {deaths}")
    if end:
        print(f" Outcome: {end.get('outcome')} in {end.get('ticks')} ticks")
    if verbose:
        for e in log[-20:]:
            print(f"   {e}")


async def _do_campaign(cli: Client, roster: list[dict]) -> None:
    stages = await cli.get("/stages")
    print("\n Stages:")
    for s in stages:
        print(f"  {s['order']}) {s['name']:<24} energy {s['energy_cost']}  rec pwr {s['recommended_power']}")
    pick = _prompt(" pick stage order: ").strip()
    try:
        order = int(pick)
    except ValueError:
        return
    stage = next((s for s in stages if s["order"] == order), None)
    if stage is None:
        print(" no such stage")
        return
    team = [h["id"] for h in roster[:3]]
    r = await cli.post("/battles", {"stage_id": stage["id"], "team": team})
    if r.status_code != 201:
        print(f" battle failed: {r.status_code} {r.text.strip()}")
        return
    b = r.json()
    print(f"\n {stage['name']}: {b['outcome']}  first_clear={b['first_clear']}")
    rew = b.get("rewards", {})
    if rew.get("gear"):
        g = rew["gear"]
        print(f"  ! gear dropped: {g['rarity']} {g['slot']} {g['stats']} (id {g['id']})")
    if rew.get("completed_daily_quest_ids"):
        print(f"  ! daily(s) completed: {rew['completed_daily_quest_ids']}")
    print(f"  rewards: coins={rew.get('coins', 0)} gems={rew.get('gems', 0)} shards={rew.get('shards', 0)}")
    _print_battle_log(b["log"])


async def _do_gear(cli: Client, roster: list[dict]) -> None:
    gear = await cli.get("/gear/mine")
    if not gear:
        print(" no gear yet — win more battles")
        return
    print(f"\n Gear ({len(gear)} items):")
    for g in gear[:30]:
        where = f"→ hero#{g['equipped_on']}" if g.get("equipped_on") else "(unequipped)"
        print(f"  #{g['id']:<4} {g['rarity']:<9} {g['slot']:<7} {g['stats']}  {where}")
    action = _prompt(" (e)quip / (u)nequip / (b)ack: ").strip().lower()
    if action == "b" or not action:
        return
    if action == "e":
        gid = _prompt(" gear id: ").strip()
        hid = _prompt(" hero id: ").strip()
        r = await cli.post(f"/gear/{gid}/equip", {"hero_instance_id": int(hid) if hid else 0})
        print(f" {r.status_code} {r.text.strip()[:120]}")
    elif action == "u":
        gid = _prompt(" gear id: ").strip()
        r = await cli.post(f"/gear/{gid}/unequip")
        print(f" {r.status_code} {r.text.strip()[:120]}")


async def _do_arena(cli: Client, roster: list[dict]) -> None:
    team = [h["id"] for h in roster[:3]]
    # Ensure we have a defense set so we can be attacked too.
    defense = await cli.get("/arena/defense")
    if not defense.get("team"):
        r = await cli.put("/arena/defense", {"team": team})
        if r.status_code == 200:
            print(" set defense team")
    opponents = await cli.get("/arena/opponents")
    if not opponents:
        print(" no opponents available — others need to set defense teams first")
        return
    print("\n Opponents:")
    for o in opponents:
        print(f"  {o['account_id']}) {o['name']:<20} rating {o['arena_rating']}  pwr {o['team_power']}")
    pick = _prompt(" attacker account id: ").strip()
    try:
        did = int(pick)
    except ValueError:
        return
    r = await cli.post("/arena/attack", {"defender_account_id": did, "team": team})
    if r.status_code != 201:
        print(f" attack failed: {r.status_code} {r.text.strip()}")
        return
    m = r.json()
    print(f"\n {m['outcome']}  delta={m['rating_delta']}  you→{m['attacker_rating_after']}")
    _print_battle_log(m["log"])


async def _do_daily(cli: Client) -> None:
    quests = await cli.get("/daily")
    print(f"\n Daily quests ({quests[0]['day_key']}):" if quests else "\n Daily: none")
    for q in quests:
        tag = q["status"]
        tgt = f" [{q['target_key']}]" if q["target_key"] else ""
        rewards = f" → {q['reward_coins']}c {q['reward_gems']}g {q['reward_shards']}s"
        print(f"  #{q['id']:<4} [{tag:<8}] {q['kind']}{tgt}  {q['progress']}/{q['goal']}{rewards}")
    if any(q["status"] == "COMPLETE" for q in quests):
        pick = _prompt(" quest id to claim (or blank): ").strip()
        if pick:
            r = await cli.post(f"/daily/{pick}/claim")
            print(f" {r.status_code} {r.text.strip()[:120]}")


async def _do_leaderboard(cli: Client) -> None:
    board = await cli.get("/arena/leaderboard")
    print("\n Leaderboard:")
    for i, e in enumerate(board, 1):
        flag = "  YOU" if e.get("account_id") == getattr(cli, "account_id", None) else ""
        print(f"  {i:>2}. {e['email']:<30} rating {e['arena_rating']}  W{e['arena_wins']}/L{e['arena_losses']}{flag}")


async def run(args: argparse.Namespace) -> int:
    email = args.email or _rand_email()
    password = args.password
    cli = Client(args.server)
    try:
        await cli.register_or_login(email, password)
        print(f" logged in: {email}")

        while True:
            me = await cli.get("/me")
            cli.account_id = me["id"]  # type: ignore[attr-defined]
            _print_header(me)
            print(" 1) Summon     2) Roster     3) Gear       4) Campaign")
            print(" 5) Arena      6) Daily      7) Leaderboard   q) Quit")
            pick = _prompt(" > ").strip().lower()
            if pick == "q" or not pick:
                return 0
            try:
                if pick == "1":
                    await _do_summon(cli)
                elif pick == "2":
                    await _show_roster(cli)
                elif pick == "3":
                    await _do_gear(cli, await _show_roster(cli))
                elif pick == "4":
                    await _do_campaign(cli, await _show_roster(cli))
                elif pick == "5":
                    await _do_arena(cli, await _show_roster(cli))
                elif pick == "6":
                    await _do_daily(cli)
                elif pick == "7":
                    await _do_leaderboard(cli)
            except httpx.HTTPStatusError as exc:
                print(f" HTTP {exc.response.status_code}: {exc.response.text}")
            except Exception as exc:  # noqa: BLE001
                print(f" err: {exc}")
    finally:
        await cli.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="hero-proto CLI")
    p.add_argument("--server", default="http://127.0.0.1:8000")
    p.add_argument("--email", default=None)
    p.add_argument("--password", default="hunter22")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
