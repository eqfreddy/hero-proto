import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.daily import on_summon
from app.db import get_db
from app.deps import get_current_account
from app.gacha import roll
from app.models import Account, GachaRecord, HeroInstance, HeroTemplate, Rarity
from app.routers.heroes import instance_out
from app.schemas import HeroInstanceOut, SummonOut

router = APIRouter(prefix="/summon", tags=["summon"])


def _pick_template(db: Session, rarity: Rarity, rng: random.Random) -> HeroTemplate:
    pool = list(db.scalars(select(HeroTemplate).where(HeroTemplate.rarity == rarity)))
    if not pool:
        # Rarity has no content yet — fall back down the ladder to guarantee a pull.
        fallback_order = [Rarity.EPIC, Rarity.RARE, Rarity.UNCOMMON, Rarity.COMMON]
        for fb in fallback_order:
            pool = list(db.scalars(select(HeroTemplate).where(HeroTemplate.rarity == fb)))
            if pool:
                break
    return rng.choice(pool)


def _do_one_pull(db: Session, account: Account, rng: random.Random) -> SummonOut:
    if account.shards < 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "not enough shards")
    result = roll(account.pulls_since_epic, rng)
    template = _pick_template(db, result.rarity, rng)
    account.shards -= 1
    account.pulls_since_epic = result.new_pity
    hero = HeroInstance(account_id=account.id, template_id=template.id, level=1, xp=0)
    db.add(hero)
    db.add(GachaRecord(
        account_id=account.id,
        template_id=template.id,
        rarity=result.rarity,
        pity_before=result.new_pity if result.new_pity > 0 else 0,
    ))
    db.flush()
    # Preload template for instance_out.
    _ = hero.template
    return SummonOut(
        hero=instance_out(hero),
        rarity=result.rarity,
        pulled_epic_pity=result.pity_triggered,
        pulls_since_epic_after=account.pulls_since_epic,
    )


@router.post("", response_model=SummonOut, status_code=status.HTTP_201_CREATED)
@router.post("/x1", response_model=SummonOut, status_code=status.HTTP_201_CREATED)
def summon_one(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SummonOut:
    """Single pull. /summon and /summon/x1 are aliases so callers can stay
    symmetric with /summon/x10."""
    rng = random.Random()
    out = _do_one_pull(db, account, rng)
    on_summon(db, account, 1)
    db.commit()
    return out


@router.post("/x10", response_model=list[SummonOut], status_code=status.HTTP_201_CREATED)
def summon_ten(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SummonOut]:
    if account.shards < 10:
        raise HTTPException(status.HTTP_409_CONFLICT, "not enough shards (need 10)")
    rng = random.Random()
    out = [_do_one_pull(db, account, rng) for _ in range(10)]
    on_summon(db, account, 10)
    db.commit()
    return out
