"""Create (or top up) a loaded test player account.

Idempotent — re-running on an existing email tops the balances back up
rather than duplicating the row. Grants a fat wallet + a full crafting
material stash + raised inventory caps + a starter roster, and marks the
account email-verified so the summon/shop gates don't block it.

Usage
-----
    uv run python -m scripts.seed_player_account kellytesting@hp.test "MouseMouse1!"
    uv run python -m scripts.seed_player_account brittesting@hp.test "MouseMouse1!"

Run against prod (machines must be awake):
    fly ssh console -C "uv run python -m scripts.seed_player_account kellytesting@hp.test 'MouseMouse1!'"
"""

from __future__ import annotations

import random
import sys

from sqlalchemy import select

from app.crafting import MATERIALS
from app.db import SessionLocal
from app.models import (
    Account,
    CraftMaterial,
    HeroInstance,
    HeroTemplate,
    Rarity,
)
from app.security import hash_password

# Fat-but-not-overflow wallet. Big enough to buy/craft/summon freely without
# tripping the soft inventory-overflow spill into the mailbox.
WALLET = {
    "gems": 500_000,
    "coins": 5_000_000,
    "shards": 50_000,
    "energy_stored": 500,
    "arena_tickets_stored": 50,
    "free_summon_credits": 200,
    "friend_points": 50_000,
    "legend_boss_shards": 300,
}
CAPS = {"hero_slot_cap": 500, "gear_slot_cap": 2_000}
MATERIAL_QTY = 999  # one stack of every crafting material
STARTER_HEROES = 6  # a handful of mid-tier heroes so the roster isn't empty


def _ensure_account(db, email: str, password: str) -> Account:
    a = db.scalar(select(Account).where(Account.email == email))
    created = a is None
    if created:
        a = Account(email=email, password_hash=hash_password(password))
        db.add(a)
        db.flush()

    # (Re)set the wallet + caps every run so a top-up is just a re-run.
    for field, value in {**WALLET, **CAPS}.items():
        setattr(a, field, value)
    a.email_verified = True
    a.password_hash = hash_password(password)  # keep password in sync on re-run

    db.flush()
    print(f"  {'+' if created else '·'} account {email} "
          f"({'created' if created else 'topped up'}) id={a.id}")
    return a


def _grant_materials(db, account: Account) -> None:
    for code in MATERIALS:
        row = db.get(CraftMaterial, {"account_id": account.id, "code": code})
        if row is None:
            db.add(CraftMaterial(account_id=account.id, code=code, quantity=MATERIAL_QTY))
        else:
            row.quantity = max(row.quantity, MATERIAL_QTY)
    print(f"    + {len(MATERIALS)} crafting materials @ {MATERIAL_QTY}")


def _grant_heroes(db, account: Account, templates: list[HeroTemplate]) -> None:
    have = db.scalar(
        select(HeroInstance).where(HeroInstance.account_id == account.id).limit(1)
    )
    if have is not None:
        print("    · roster already populated, skipping starter heroes")
        return
    rng = random.Random(account.id)
    chosen = rng.sample(templates, k=min(STARTER_HEROES, len(templates)))
    for t in chosen:
        db.add(HeroInstance(
            account_id=account.id,
            template_id=t.id,
            level=30,
            stars=4,
            special_level=4,
        ))
    print(f"    + {len(chosen)} starter heroes (lvl 30, 4-star)")


def main(email: str, password: str) -> int:
    db = SessionLocal()
    try:
        templates = list(db.scalars(
            select(HeroTemplate).where(HeroTemplate.rarity.in_([
                Rarity.RARE, Rarity.EPIC, Rarity.LEGENDARY,
            ]))
        ))
        if len(templates) < STARTER_HEROES:
            print("FATAL: not enough hero templates — run app.seed first.")
            return 1

        print(f"Seeding loaded account: {email}")
        account = _ensure_account(db, email, password)
        _grant_materials(db, account)
        _grant_heroes(db, account, templates)

        db.commit()
        print(f"\n✓ {email} ready. gems={WALLET['gems']:,} coins={WALLET['coins']:,} "
              f"shards={WALLET['shards']:,} — buy/craft/summon away.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: uv run python -m scripts.seed_player_account <email> <password>")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
