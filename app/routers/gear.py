import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crafting import SALVAGE_YIELDS, grant_material
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, Gear, GearRarity, GearSet, GearSlot, HeroInstance
from app.schemas import EquipIn, GearOut

router = APIRouter(prefix="/gear", tags=["gear"])


def gear_out(g: Gear) -> GearOut:
    try:
        stats = json.loads(g.stats_json or "{}")
    except json.JSONDecodeError:
        stats = {}
    return GearOut(
        id=g.id,
        slot=GearSlot(g.slot) if not isinstance(g.slot, GearSlot) else g.slot,
        rarity=GearRarity(g.rarity) if not isinstance(g.rarity, GearRarity) else g.rarity,
        set=GearSet(g.set_code) if not isinstance(g.set_code, GearSet) else g.set_code,
        stats=stats,
        equipped_on=g.hero_instance_id,
        locked=bool(g.locked),
        name=g.name,
        flavor=g.flavor,
    )


def _get_own_gear(db: Session, account: Account, gear_id: int) -> Gear:
    g = db.get(Gear, gear_id)
    if g is None or g.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gear not found")
    return g


@router.get("/mine", response_model=list[GearOut])
def list_mine(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 500,
    offset: int = 0,
) -> list[GearOut]:
    """Player's gear inventory, newest-first. Bounded like /heroes/mine so
    endgame inventories don't produce a 10MB response."""
    limit = max(1, min(1000, limit))
    offset = max(0, offset)
    rows = db.scalars(
        select(Gear)
        .where(Gear.account_id == account.id)
        .order_by(Gear.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [gear_out(g) for g in rows]


@router.post("/{gear_id}/equip", response_model=GearOut)
def equip(
    gear_id: int,
    body: EquipIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GearOut:
    g = _get_own_gear(db, account, gear_id)
    hero = db.get(HeroInstance, body.hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")

    # Unequip anything the hero already has in this slot.
    existing_in_slot = db.scalar(
        select(Gear).where(
            Gear.hero_instance_id == hero.id,
            Gear.slot == g.slot,
            Gear.id != g.id,
        )
    )
    if existing_in_slot is not None:
        existing_in_slot.hero_instance_id = None

    g.hero_instance_id = hero.id
    db.commit()
    db.refresh(g)
    return gear_out(g)


@router.post("/{gear_id}/unequip", response_model=GearOut)
def unequip(
    gear_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GearOut:
    g = _get_own_gear(db, account, gear_id)
    g.hero_instance_id = None
    db.commit()
    db.refresh(g)
    return gear_out(g)


@router.post("/{gear_id}/lock")
def toggle_lock(
    gear_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Toggle the locked flag. Locked gear cannot be salvaged."""
    g = _get_own_gear(db, account, gear_id)
    g.locked = not g.locked
    db.commit()
    return {"id": g.id, "locked": g.locked}


@router.post("/{gear_id}/salvage", status_code=status.HTTP_200_OK)
def salvage(
    gear_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Break down a gear piece into crafting materials.
    Named and locked gear cannot be salvaged. Equipped gear is auto-unequipped.
    """
    g = _get_own_gear(db, account, gear_id)

    if g.name:
        raise HTTPException(status.HTTP_409_CONFLICT, "named gear cannot be salvaged")
    if g.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "unlock the gear before salvaging")

    rarity = GearRarity(g.rarity) if not isinstance(g.rarity, GearRarity) else g.rarity
    yields = SALVAGE_YIELDS.get(rarity, {})

    # Auto-unequip.
    g.hero_instance_id = None

    # Grant materials.
    materials_granted: dict[str, int] = {}
    for code, qty in yields.items():
        if code == "coins":
            if qty > 0:
                account.coins = (account.coins or 0) + qty
                materials_granted["coins"] = qty
        elif qty > 0:
            grant_material(db, account, code, qty)
            materials_granted[code] = qty

    db.delete(g)
    db.commit()
    return {"salvaged_gear_id": gear_id, "rarity": str(rarity), "yielded": materials_granted}
