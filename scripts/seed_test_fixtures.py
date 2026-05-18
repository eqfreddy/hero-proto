"""Seed arena bots + a test guild around a target account.

Idempotent — re-running adjusts existing fixtures in place rather than
duplicating. Designed to be runnable both locally and via `fly ssh
console -C "uv run python -m scripts.seed_test_fixtures hello@zombiesub.com"`.

What it does
============

1.  Creates 10 bot accounts (bot01..bot10@hp.test) with arena ratings
    laddered around the target (-1000 .. +1000 in 200-step increments).
2.  Grants each bot 4 hero instances from random LEGENDARY / EPIC / RARE
    templates, then writes a 3-hero DefenseTeam so they're matchmaker-
    eligible.
3.  Creates a guild "[NULL_POINTER]" (tag: NP) with the target account
    as LEADER and 4 of the bots as MEMBERS.
4.  Prints a summary table.

Usage
-----
    uv run python -m scripts.seed_test_fixtures hello@zombiesub.com

Bot password is constant (BOT_PASSWORD below) — convenient for poking
their accounts via /auth/login if you ever need to.
"""

from __future__ import annotations

import json
import random
import sys

from sqlalchemy import select

from app.combat import unit_power
from app.db import SessionLocal
from app.models import (
    Account,
    DefenseTeam,
    Guild,
    GuildMember,
    GuildRole,
    HeroInstance,
    HeroTemplate,
    Rarity,
)
from app.routers.battles import _unit_from_instance
from app.security import hash_password

BOT_EMAIL_FMT = "bot{:02d}@hp.test"
BOT_PASSWORD = "BotPass123!"
BOT_RATING_OFFSETS = [-1000, -800, -600, -400, -200, 200, 400, 600, 800, 1000]
GUILD_NAME = "[NULL_POINTER]"
GUILD_TAG = "NP"
GUILD_DESC = "Test guild — automated fixtures. Spawned by seed_test_fixtures."


def _ensure_account(db, email: str, *, rating: int) -> Account:
    a = db.scalar(select(Account).where(Account.email == email))
    if a is None:
        a = Account(
            email=email,
            password_hash=hash_password(BOT_PASSWORD),
            arena_rating=rating,
            gems=100,
            coins=5000,
            shards=20,
            energy_stored=50,
            arena_tickets_stored=5,
        )
        db.add(a)
        db.flush()
        print(f"  + account {email} created (id={a.id})")
    else:
        a.arena_rating = rating
        print(f"  · account {email} exists (id={a.id}), rating→{rating}")
    return a


def _grant_heroes(db, bot: Account, templates: list[HeroTemplate], target_power: int) -> list[HeroInstance]:
    existing = list(db.scalars(select(HeroInstance).where(HeroInstance.account_id == bot.id)))
    if existing:
        print(f"    · already has {len(existing)} heroes, reusing")
        return existing

    # Stars/level scaling tuned so a 4-hero roster totals roughly target_power.
    # 4 heroes * scale_stat(base, lvl, stars) ≈ target_power.
    # Rough: level 30, stars 4 → ~3500 power per legendary. Adjust by target.
    star_map = {500: 1, 1000: 2, 2000: 3, 3500: 4, 5000: 5}
    closest_pow = min(star_map.keys(), key=lambda k: abs(k - target_power))
    stars = star_map[closest_pow]
    level = min(35, 10 + stars * 5)

    chosen = random.sample(templates, k=min(4, len(templates)))
    heroes: list[HeroInstance] = []
    for t in chosen:
        h = HeroInstance(
            account_id=bot.id,
            template_id=t.id,
            level=level,
            stars=stars,
            special_level=min(5, stars),
        )
        db.add(h)
        heroes.append(h)
    db.flush()
    print(f"    + granted {len(heroes)} heroes (lvl {level}, {stars}★)")
    return heroes


def _set_defense_team(db, bot: Account, heroes: list[HeroInstance]) -> int:
    team = heroes[:3]
    total_power = 0
    for idx, h in enumerate(team):
        try:
            unit = _unit_from_instance(h, "B", idx)
            total_power += unit_power(unit)
        except Exception as exc:  # noqa: BLE001
            print(f"    ! power calc failed for hero {h.id}: {exc}")
    hero_ids = [h.id for h in team]
    existing = db.get(DefenseTeam, bot.id)
    if existing is None:
        db.add(DefenseTeam(
            account_id=bot.id,
            hero_ids_json=json.dumps(hero_ids),
            power=total_power,
        ))
    else:
        existing.hero_ids_json = json.dumps(hero_ids)
        existing.power = total_power
    print(f"    + defense team set (power={total_power})")
    return total_power


def _ensure_guild(db, target: Account, bots: list[Account]) -> Guild:
    g = db.scalar(select(Guild).where(Guild.name == GUILD_NAME))
    if g is None:
        g = Guild(name=GUILD_NAME, tag=GUILD_TAG, description=GUILD_DESC)
        db.add(g)
        db.flush()
        print(f"  + guild '{GUILD_NAME}' created (id={g.id})")
    else:
        print(f"  · guild '{GUILD_NAME}' exists (id={g.id})")

    # Wipe any stale memberships that conflict (target or chosen bots
    # already in some other guild) so this seed is idempotent.
    members_needed = [target] + bots[:4]
    for a in members_needed:
        existing = db.scalar(select(GuildMember).where(GuildMember.account_id == a.id))
        if existing and existing.guild_id != g.id:
            db.delete(existing)
            db.flush()
            print(f"    · {a.email} was in guild {existing.guild_id}, removed")

    for idx, a in enumerate(members_needed):
        existing = db.scalar(select(GuildMember).where(GuildMember.account_id == a.id))
        role = GuildRole.LEADER if idx == 0 else GuildRole.MEMBER
        if existing is None:
            db.add(GuildMember(account_id=a.id, guild_id=g.id, role=role))
            print(f"    + {a.email} added as {role}")
        else:
            if existing.role != role:
                existing.role = role
            if existing.guild_id != g.id:
                existing.guild_id = g.id
            print(f"    · {a.email} already in guild as {role}")
    return g


def main(target_email: str) -> int:
    db = SessionLocal()
    try:
        target = db.scalar(select(Account).where(Account.email == target_email))
        if target is None:
            print(f"FATAL: account {target_email!r} not found. Sign up first.")
            return 1
        print(f"Target: {target.email} (id={target.id}, rating={target.arena_rating})")

        # Pool: keep templates with non-empty roster-relevant stats.
        templates = list(db.scalars(
            select(HeroTemplate).where(HeroTemplate.rarity.in_([
                Rarity.RARE, Rarity.EPIC, Rarity.LEGENDARY,
            ]))
        ))
        if len(templates) < 4:
            print("FATAL: not enough templates seeded — run app.seed first.")
            return 1
        print(f"Template pool: {len(templates)} RARE+/EPIC+/LEG.")

        rng = random.Random(42)
        bots: list[Account] = []
        for i, offset in enumerate(BOT_RATING_OFFSETS, start=1):
            email = BOT_EMAIL_FMT.format(i)
            rating = max(800, target.arena_rating + offset)
            target_power = 500 + (i - 1) * 500  # ladder: 500..5000
            print(f"\nBot {i:02d}: {email} (rating {rating}, target_power {target_power})")
            bot = _ensure_account(db, email, rating=rating)
            rng.shuffle(templates)
            heroes = _grant_heroes(db, bot, templates, target_power)
            _set_defense_team(db, bot, heroes)
            bots.append(bot)

        print(f"\nGuild setup:")
        _ensure_guild(db, target, bots)

        db.commit()
        print("\n✓ Fixtures seeded. Re-run is idempotent.")
        print("  Arena opponents will populate next /arena/opponents request.")
        print(f"  Guild '{GUILD_NAME}' has you + 4 bots; remaining 6 bots are unguilded.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python -m scripts.seed_test_fixtures <target_email>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
