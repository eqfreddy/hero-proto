"""Inventory cap status, expansion purchase, mailbox claim/dismiss.

  GET  /inventory/usage              hero/gear used + cap, expansion price
  POST /inventory/expand/{kind}      buy +N slots with gems (kind = hero|gear)
  GET  /inventory/mailbox            list overflow items waiting to be claimed
  POST /inventory/mailbox/{idx}/claim   redeem one item, persists to inventory
  POST /inventory/mailbox/{idx}/dismiss drop a mailbox item permanently
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.inventory import (
    expand_cap,
    gear_usage,
    hero_usage,
    list_mailbox,
    pop_mailbox,
)
from app.models import Account, Gear, GearRarity, GearSet, GearSlot, HeroInstance

router = APIRouter(prefix="/inventory", tags=["inventory"])


class SlotUsageOut(BaseModel):
    used: int
    cap: int
    remaining: int
    full: bool


class InventoryUsageOut(BaseModel):
    hero: SlotUsageOut
    gear: SlotUsageOut
    expansion_step: int
    expansion_cost_gems: int
    cap_max: int
    mailbox_count: int


class ExpandOut(BaseModel):
    kind: str
    new_cap: int
    gems_spent: int
    gems_after: int


class MailboxItemOut(BaseModel):
    idx: int
    kind: str
    payload: dict
    ts: str


class MailboxClaimOut(BaseModel):
    idx: int
    kind: str
    granted: dict


@router.get("/usage", response_model=InventoryUsageOut)
def get_usage(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryUsageOut:
    h = hero_usage(db, account)
    g = gear_usage(db, account)
    return InventoryUsageOut(
        hero=SlotUsageOut(used=h.used, cap=h.cap, remaining=h.remaining, full=h.full),
        gear=SlotUsageOut(used=g.used, cap=g.cap, remaining=g.remaining, full=g.full),
        expansion_step=settings.slot_expansion_step,
        expansion_cost_gems=settings.slot_expansion_cost_gems,
        cap_max=settings.slot_cap_max,
        mailbox_count=len(list_mailbox(account)),
    )


@router.post("/expand/{kind}", response_model=ExpandOut, status_code=status.HTTP_201_CREATED)
def expand_inventory(
    kind: str,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> ExpandOut:
    if kind not in ("hero", "gear"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be 'hero' or 'gear'")
    try:
        new_cap, spent, after = expand_cap(account, kind)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    return ExpandOut(kind=kind, new_cap=new_cap, gems_spent=spent, gems_after=after)


@router.get("/mailbox", response_model=list[MailboxItemOut])
def get_mailbox(
    account: Annotated[Account, Depends(get_current_account)],
) -> list[MailboxItemOut]:
    return [MailboxItemOut(**item) for item in list_mailbox(account)]


@router.post("/mailbox/{idx}/claim", response_model=MailboxClaimOut, status_code=status.HTTP_201_CREATED)
def claim_mailbox(
    idx: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> MailboxClaimOut:
    """Claim one mailbox entry. If the relevant slot is still full, 409 — the
    player has to expand or sell first. Idempotent against double-claim because
    pop_mailbox returns None on out-of-range indices.
    """
    items = list_mailbox(account)
    if idx < 0 or idx >= len(items):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mailbox item not found")
    target = items[idx]
    kind = target["kind"]

    # Check capacity BEFORE popping so we don't lose the item on a 409.
    if kind == "hero":
        usage = hero_usage(db, account)
        if usage.full:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"hero inventory full ({usage.used}/{usage.cap}) — expand first")
        item = pop_mailbox(account, idx)
        payload = item["payload"]
        hero = HeroInstance(
            account_id=account.id,
            template_id=int(payload["template_id"]),
            level=int(payload.get("level", 1)),
        )
        db.add(hero)
        db.flush()
        granted = {"hero_instance_id": hero.id}
    elif kind == "gear":
        usage = gear_usage(db, account)
        if usage.full:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"gear inventory full ({usage.used}/{usage.cap}) — expand or sell first")
        item = pop_mailbox(account, idx)
        payload = item["payload"]
        try:
            slot = GearSlot(payload["slot"])
            rarity = GearRarity(payload["rarity"])
            set_code = GearSet(payload["set_code"])
        except (ValueError, KeyError) as e:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                f"corrupt mailbox gear payload: {e}") from e
        g = Gear(
            account_id=account.id,
            slot=slot, rarity=rarity, set_code=set_code,
            stats_json=json.dumps(payload.get("stats", {})),
        )
        db.add(g)
        db.flush()
        granted = {"gear_id": g.id, "slot": str(slot), "rarity": str(rarity)}
    else:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"unknown mailbox kind {kind!r}")

    db.commit()
    return MailboxClaimOut(idx=idx, kind=kind, granted=granted)


@router.post("/mailbox/{idx}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_mailbox(
    idx: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Throw away a mailbox entry without claiming. Useful for junk drops."""
    item = pop_mailbox(account, idx)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mailbox item not found")
    db.commit()
    return None
