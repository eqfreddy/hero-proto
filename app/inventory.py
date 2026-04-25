"""Inventory cap enforcement + mailbox overflow.

Capped resources today: HeroInstance (per Account.hero_slot_cap) and Gear
(per Account.gear_slot_cap). Soft-enforced via mailbox overflow:

  - Drop fits: persist normally, mailbox untouched.
  - Drop doesn't fit: don't persist; queue {kind, payload} into
    mailbox_overflow_json. Player redeems later from the inventory tab.

Why soft: hard-rejecting a gacha pull or a battle gear drop is the worst
possible UX. Players who hit cap should still see the "you got X!" toast,
just with a "claim from mailbox" CTA when they make room.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Account, Gear, HeroInstance, utcnow


@dataclass
class SlotUsage:
    used: int
    cap: int

    @property
    def remaining(self) -> int:
        return max(0, self.cap - self.used)

    @property
    def full(self) -> bool:
        return self.used >= self.cap


def hero_usage(db: Session, account: Account) -> SlotUsage:
    used = db.scalar(
        select(func.count(HeroInstance.id)).where(HeroInstance.account_id == account.id)
    ) or 0
    return SlotUsage(used=int(used), cap=int(account.hero_slot_cap or settings.hero_slot_cap_default))


def gear_usage(db: Session, account: Account) -> SlotUsage:
    used = db.scalar(
        select(func.count(Gear.id)).where(Gear.account_id == account.id)
    ) or 0
    return SlotUsage(used=int(used), cap=int(account.gear_slot_cap or settings.gear_slot_cap_default))


# --- Mailbox -----------------------------------------------------------------


def _read_mailbox(account: Account) -> list[dict]:
    try:
        data = json.loads(account.mailbox_overflow_json or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _write_mailbox(account: Account, items: list[dict]) -> None:
    account.mailbox_overflow_json = json.dumps(items, separators=(",", ":"))


def queue_mailbox(account: Account, kind: str, payload: dict) -> None:
    """Stash an overflow item in the player's mailbox. Used when an inventory
    cap blocks the immediate persist."""
    items = _read_mailbox(account)
    items.append({
        "kind": kind,
        "payload": payload,
        "ts": utcnow().isoformat(),
    })
    _write_mailbox(account, items)


def list_mailbox(account: Account) -> list[dict]:
    """Surface the mailbox to the API. Order: oldest first so players claim
    in the order things accumulated."""
    out = []
    for i, item in enumerate(_read_mailbox(account)):
        out.append({
            "idx": i,
            "kind": item.get("kind", ""),
            "payload": item.get("payload", {}),
            "ts": item.get("ts", ""),
        })
    return out


def pop_mailbox(account: Account, idx: int) -> dict | None:
    """Remove + return one mailbox entry. Returns None if idx is out of range."""
    items = _read_mailbox(account)
    if idx < 0 or idx >= len(items):
        return None
    item = items.pop(idx)
    _write_mailbox(account, items)
    return item


# --- Cap-aware persistence helpers -------------------------------------------


def try_persist_hero(db: Session, account: Account, template_id: int, *, level: int = 1) -> int | None:
    """Persist a HeroInstance if there's room; otherwise mailbox the grant.

    Returns the new HeroInstance.id, or None if it went to mailbox.
    Caller commits.
    """
    usage = hero_usage(db, account)
    if usage.full:
        queue_mailbox(account, "hero", {"template_id": template_id, "level": level})
        return None
    hero = HeroInstance(account_id=account.id, template_id=template_id, level=level)
    db.add(hero)
    db.flush()
    return hero.id


def try_persist_gear(db: Session, account: Account, slot, rarity, set_code, stats: dict) -> int | None:
    """Persist a Gear row if there's room; otherwise mailbox the drop."""
    import json as _json
    usage = gear_usage(db, account)
    if usage.full:
        queue_mailbox(account, "gear", {
            "slot": str(slot), "rarity": str(rarity), "set_code": str(set_code),
            "stats": stats,
        })
        return None
    g = Gear(
        account_id=account.id,
        slot=slot, rarity=rarity, set_code=set_code,
        stats_json=_json.dumps(stats),
    )
    db.add(g)
    db.flush()
    return g.id


# --- Cap expansion -----------------------------------------------------------


def expand_cap(account: Account, kind: str) -> tuple[int, int, int]:
    """Buy one expansion (slot_expansion_step slots) for `slot_expansion_cost_gems`.
    `kind` is "hero" or "gear". Returns (new_cap, gems_spent, gems_after).
    Raises ValueError on insufficient funds or hard-cap hit. Caller commits.
    """
    cap_attr = "hero_slot_cap" if kind == "hero" else "gear_slot_cap"
    current = int(getattr(account, cap_attr))
    if current >= settings.slot_cap_max:
        raise ValueError(f"slot cap already at hard maximum ({settings.slot_cap_max})")
    cost = settings.slot_expansion_cost_gems
    if account.gems < cost:
        raise ValueError(f"need {cost} gems (have {account.gems})")
    new_cap = min(settings.slot_cap_max, current + settings.slot_expansion_step)
    setattr(account, cap_attr, new_cap)
    account.gems -= cost
    return new_cap, cost, account.gems
