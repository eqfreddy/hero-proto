import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.combat import level_cap_for_stars, power_rating, scale_stat
from app.db import get_db
from app.deps import get_current_account
from app.gear_logic import completed_sets, gear_bonus_for
from app.models import Account, HeroInstance, HeroTemplate, Rarity
from app.schemas import AscendIn, HeroInstanceOut, HeroTemplateOut, SkillUpIn

router = APIRouter(prefix="/heroes", tags=["heroes"])


def _template_out(t: HeroTemplate) -> HeroTemplateOut:
    try:
        special = json.loads(t.special_json or "null")
    except json.JSONDecodeError:
        special = None
    return HeroTemplateOut(
        id=t.id,
        code=t.code,
        name=t.name,
        rarity=Rarity(t.rarity) if not isinstance(t.rarity, Rarity) else t.rarity,
        faction=t.faction,
        role=t.role,
        base_hp=t.base_hp,
        base_atk=t.base_atk,
        base_def=t.base_def,
        base_spd=t.base_spd,
        basic_mult=t.basic_mult,
        special_cooldown=t.special_cooldown,
        special=special,
    )


def instance_out(h: HeroInstance) -> HeroInstanceOut:
    t = h.template
    hp = scale_stat(t.base_hp, h.level, h.stars)
    atk = scale_stat(t.base_atk, h.level, h.stars)
    df = scale_stat(t.base_def, h.level, h.stars)
    spd = t.base_spd
    bonus = gear_bonus_for(h)
    hp += bonus["hp"]
    atk += bonus["atk"]
    df += bonus["def"]
    spd += bonus["spd"]
    pct = bonus.get("pct", {})
    if pct:
        hp = int(round(hp * (1.0 + pct.get("hp", 0.0))))
        atk = int(round(atk * (1.0 + pct.get("atk", 0.0))))
        df = int(round(df * (1.0 + pct.get("def", 0.0))))
        spd = int(round(spd * (1.0 + pct.get("spd", 0.0))))
    equipped_ids = [g.id for g in h.gear]
    return HeroInstanceOut(
        id=h.id,
        template=_template_out(t),
        level=h.level,
        level_cap=level_cap_for_stars(h.stars),
        xp=h.xp,
        special_level=h.special_level,
        stars=h.stars,
        hp=hp,
        atk=atk,
        **{"def": df},
        spd=spd,
        power=power_rating(hp, atk, df, spd),
        equipped_gear_ids=equipped_ids,
        active_sets=completed_sets(h),
    )


@router.get("/templates", response_model=list[HeroTemplateOut])
def list_templates(db: Annotated[Session, Depends(get_db)]) -> list[HeroTemplateOut]:
    return [_template_out(t) for t in db.scalars(select(HeroTemplate).order_by(HeroTemplate.id))]


@router.get("/mine", response_model=list[HeroInstanceOut])
def list_mine(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[HeroInstanceOut]:
    rows = db.scalars(
        select(HeroInstance).where(HeroInstance.account_id == account.id).order_by(HeroInstance.id.desc())
    )
    return [instance_out(h) for h in rows]


MAX_SPECIAL_LEVEL = 5


@router.post("/{hero_instance_id}/skill_up", response_model=HeroInstanceOut)
def skill_up(
    hero_instance_id: int,
    body: SkillUpIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HeroInstanceOut:
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")
    if hero.special_level >= MAX_SPECIAL_LEVEL:
        raise HTTPException(status.HTTP_409_CONFLICT, "already at max special level")

    # Fodder must be owned, distinct, same template, not this hero.
    fodder_ids = list(dict.fromkeys(body.fodder_ids))  # dedup preserving order
    if hero.id in fodder_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot feed hero into itself")
    fodder: list[HeroInstance] = []
    for fid in fodder_ids:
        f = db.get(HeroInstance, fid)
        if f is None or f.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"fodder {fid} not owned")
        if f.template_id != hero.template_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"fodder {fid} is a different hero template")
        if f.gear:
            raise HTTPException(status.HTTP_409_CONFLICT, f"fodder {fid} still has gear equipped")
        fodder.append(f)

    available_levels = MAX_SPECIAL_LEVEL - hero.special_level
    if len(fodder) > available_levels:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"too many fodder: can gain at most {available_levels} levels",
        )

    hero.special_level += len(fodder)
    for f in fodder:
        db.delete(f)
    db.commit()
    db.refresh(hero)
    return instance_out(hero)


MAX_STARS = 5


@router.post("/{hero_instance_id}/ascend", response_model=HeroInstanceOut)
def ascend(
    hero_instance_id: int,
    body: AscendIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HeroInstanceOut:
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")
    if hero.stars >= MAX_STARS:
        raise HTTPException(status.HTTP_409_CONFLICT, "already at max stars")

    # Ascending from N to N+1 requires exactly N fodder heroes of the same template
    # (so 1->2 needs 1, 2->3 needs 2, etc.). Caller can also jump multiple tiers by
    # providing the sum: n + (n+1) + ... fodder. Simplest: advance one tier at a time.
    fodder_ids = list(dict.fromkeys(body.fodder_ids))
    if hero.id in fodder_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot feed hero into itself")
    fodder: list[HeroInstance] = []
    for fid in fodder_ids:
        f = db.get(HeroInstance, fid)
        if f is None or f.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"fodder {fid} not owned")
        if f.template_id != hero.template_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"fodder {fid} different template")
        if f.gear:
            raise HTTPException(status.HTTP_409_CONFLICT, f"fodder {fid} still has gear equipped")
        fodder.append(f)

    needed = hero.stars  # N fodder to go from N to N+1
    if len(fodder) != needed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"need exactly {needed} fodder to ascend {hero.stars}* -> {hero.stars + 1}*",
        )

    hero.stars += 1
    for f in fodder:
        db.delete(f)
    db.commit()
    db.refresh(hero)
    return instance_out(hero)
