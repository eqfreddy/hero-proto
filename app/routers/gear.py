import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    )


@router.get("/mine", response_model=list[GearOut])
def list_mine(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GearOut]:
    rows = db.scalars(select(Gear).where(Gear.account_id == account.id).order_by(Gear.id.desc()))
    return [gear_out(g) for g in rows]


@router.post("/{gear_id}/equip", response_model=GearOut)
def equip(
    gear_id: int,
    body: EquipIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GearOut:
    g = db.get(Gear, gear_id)
    if g is None or g.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gear not found")
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
    g = db.get(Gear, gear_id)
    if g is None or g.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gear not found")
    g.hero_instance_id = None
    db.commit()
    db.refresh(g)
    return gear_out(g)
