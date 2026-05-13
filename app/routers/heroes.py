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
from app.schemas import HeroInstanceOut, HeroTemplateOut

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
    # Phase 2.2 variance — per-stat % offset, applied to the *base* scaled
    # stat before gear so a +10% atk roll feels equally meaningful at
    # level 1 and level 60. Empty {} means first copy / pre-Phase-2.2.
    from app.gacha import parse_variance
    variance = parse_variance(h.variance_pct_json)
    if variance:
        hp = int(round(hp * (1.0 + variance.get("hp", 0.0))))
        atk = int(round(atk * (1.0 + variance.get("atk", 0.0))))
        df = int(round(df * (1.0 + variance.get("def", 0.0))))
        spd = int(round(spd * (1.0 + variance.get("spd", 0.0))))
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
        variance_pct=variance,
    )


@router.get("/templates", response_model=list[HeroTemplateOut])
def list_templates(db: Annotated[Session, Depends(get_db)]) -> list[HeroTemplateOut]:
    return [_template_out(t) for t in db.scalars(select(HeroTemplate).order_by(HeroTemplate.id))]


@router.get("/mine", response_model=list[HeroInstanceOut])
def list_mine(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 500,
    offset: int = 0,
) -> list[HeroInstanceOut]:
    """Player's owned heroes, newest-first. Endgame accounts can accumulate
    thousands; a per-call cap keeps the response bounded. Roster-builder UIs
    that want everything can page via offset."""
    limit = max(1, min(1000, limit))
    offset = max(0, offset)
    rows = db.scalars(
        select(HeroInstance)
        .where(HeroInstance.account_id == account.id)
        .order_by(HeroInstance.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [instance_out(h) for h in rows]


MAX_SPECIAL_LEVEL = 5


@router.post("/{hero_instance_id}/skill_up", response_model=HeroInstanceOut)
def skill_up(
    hero_instance_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HeroInstanceOut:
    """Spend template shards to bump a hero's special_level by 1.

    Replaces the fodder-based model as of the 2026-05-12 shard remap
    (see docs/superpowers/plans/2026-05-12-shard-remap.md). Costs come
    from `SHARDS_TO_SKILL_UP`; the player's roster is no longer touched.
    """
    from app.template_shards import shards_for_skill_up, get_shards, spend
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")
    if hero.special_level >= MAX_SPECIAL_LEVEL:
        raise HTTPException(status.HTTP_409_CONFLICT, "already at max special level")

    cost = shards_for_skill_up(hero.special_level)
    if cost is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"no shard cost defined for special level {hero.special_level}",
        )
    if not spend(account, hero.template.code, cost):
        have = get_shards(account, hero.template.code)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"need {cost} {hero.template.code} shards, have {have}",
        )

    hero.special_level += 1
    db.commit()
    db.refresh(hero)
    return instance_out(hero)


MAX_STARS = 6


@router.post("/{hero_instance_id}/ascend-with-shards", response_model=HeroInstanceOut)
def ascend_with_shards(
    hero_instance_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HeroInstanceOut:
    """Spend template shards to ascend instead of feeding duplicate heroes.

    Shards are auto-granted on duplicate gacha pulls; this endpoint is the
    sink. Cost scales by current star tier (10 / 30 / 80 / 200 / 500)."""
    from app.template_shards import shards_for_ascension, get_shards, spend
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")
    if hero.stars >= MAX_STARS:
        raise HTTPException(status.HTTP_409_CONFLICT, "already at max stars")
    cost = shards_for_ascension(hero.stars)
    if cost is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no shard cost defined for this star tier")
    if not spend(account, hero.template.code, cost):
        have = get_shards(account, hero.template.code)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"need {cost} {hero.template.code} shards, have {have}",
        )
    hero.stars += 1
    db.commit()
    db.refresh(hero)
    return instance_out(hero)


@router.get("/template-shards", response_model=dict[str, int])
def list_template_shards(
    account: Annotated[Account, Depends(get_current_account)],
) -> dict[str, int]:
    """Return all template-shard balances. UI uses this to badge ascendable
    heroes in the roster."""
    from app.template_shards import get_all_shards
    return get_all_shards(account)


# --- Sell hero ---------------------------------------------------------------
#
# Inventory pressure relief — players accumulate dupes and need a way to
# convert them to currency without ascending. Coin + shard payouts scale by
# rarity + level + stars. Equipped gear auto-unequips before delete.

from pydantic import BaseModel as _BM

_SELL_COIN_BY_RARITY = {
    Rarity.COMMON: 50,
    Rarity.UNCOMMON: 120,
    Rarity.RARE: 280,
    Rarity.EPIC: 600,
    Rarity.LEGENDARY: 1500,
    Rarity.MYTH: 3000,
}
_SELL_SHARD_BY_RARITY = {
    Rarity.COMMON: 0,
    Rarity.UNCOMMON: 1,
    Rarity.RARE: 3,
    Rarity.EPIC: 6,
    Rarity.LEGENDARY: 15,
    Rarity.MYTH: 30,
}


def _sell_value(hero: HeroInstance) -> tuple[int, int]:
    """Returns (coins, shards) the player gets when selling this hero.

    Base from rarity + 5% per level above 1 + 25% per star above 1. Keeps
    sell-then-resummon strictly worse than holding for ascension fodder.
    """
    rarity = Rarity(hero.template.rarity) if not isinstance(hero.template.rarity, Rarity) else hero.template.rarity
    base_coins = _SELL_COIN_BY_RARITY.get(rarity, 50)
    base_shards = _SELL_SHARD_BY_RARITY.get(rarity, 0)
    level_mult = 1.0 + 0.05 * max(0, hero.level - 1)
    star_mult = 1.0 + 0.25 * max(0, hero.stars - 1)
    coins = int(round(base_coins * level_mult * star_mult))
    shards = int(round(base_shards * star_mult))
    return coins, shards


class SellPreviewOut(_BM):
    hero_instance_id: int
    coins: int
    shards: int
    rarity: str
    level: int
    stars: int


class SellOut(_BM):
    sold_hero_instance_id: int
    coins_granted: int
    shards_granted: int
    coins: int
    shards: int


# --- Next-upgrade preview ----------------------------------------------------
#
# Phase 2.1 — give the roster page numbers to chase. Returns the *current*
# computed stats alongside the *projected* stats after each available
# upgrade path: level-up (XP-driven, via /battles), star-up (via
# /ascend-with-shards), special-up (via /skill_up — now shard-based as
# of the 2026-05-12 remap). Read-only.
#
# We keep the math here in step with instance_out (variance + gear + sets)
# so a player sees the same numbers on the detail page that the battle
# resolver will use.


class UpgradePreview(_BM):
    available: bool                 # is this upgrade legal right now
    cost: dict                      # what would be spent / required
    delta: dict[str, int]           # stat delta vs current (hp/atk/def/spd/power)
    after: dict[str, int]           # absolute stats after the upgrade


class HeroPreviewOut(_BM):
    hero_instance_id: int
    current: dict[str, int]         # hp/atk/def/spd/power right now
    level_up: UpgradePreview
    star_up: UpgradePreview
    special_up: UpgradePreview


def _project(
    h: HeroInstance,
    *,
    level: int | None = None,
    stars: int | None = None,
) -> dict[str, int]:
    """Recompute stats as if (level, stars) were applied. Pure — never
    mutates the row."""
    from app.gacha import parse_variance

    t = h.template
    use_level = level if level is not None else h.level
    use_stars = stars if stars is not None else h.stars
    hp = scale_stat(t.base_hp, use_level, use_stars)
    atk = scale_stat(t.base_atk, use_level, use_stars)
    df = scale_stat(t.base_def, use_level, use_stars)
    spd = t.base_spd
    variance = parse_variance(h.variance_pct_json)
    if variance:
        hp = int(round(hp * (1.0 + variance.get("hp", 0.0))))
        atk = int(round(atk * (1.0 + variance.get("atk", 0.0))))
        df = int(round(df * (1.0 + variance.get("def", 0.0))))
        spd = int(round(spd * (1.0 + variance.get("spd", 0.0))))
    bonus = gear_bonus_for(h)
    hp += bonus["hp"]; atk += bonus["atk"]; df += bonus["def"]; spd += bonus["spd"]
    pct = bonus.get("pct", {})
    if pct:
        hp = int(round(hp * (1.0 + pct.get("hp", 0.0))))
        atk = int(round(atk * (1.0 + pct.get("atk", 0.0))))
        df = int(round(df * (1.0 + pct.get("def", 0.0))))
        spd = int(round(spd * (1.0 + pct.get("spd", 0.0))))
    return {
        "hp": hp, "atk": atk, "def": df, "spd": spd,
        "power": power_rating(hp, atk, df, spd),
    }


def _delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {k: int(after.get(k, 0)) - int(before.get(k, 0)) for k in before}


@router.get("/{hero_instance_id}/preview", response_model=HeroPreviewOut)
def upgrade_preview(
    hero_instance_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HeroPreviewOut:
    """Show the player what each available upgrade would do — Phase 2.1
    chase-the-numbers UX. Returns deltas + absolute after-stats for level,
    star, and special. `available=False` means the upgrade path is capped
    or otherwise impossible right now."""
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")

    current = _project(hero)

    # Level up — earned via battle XP, capped by stars-derived ceiling.
    # We show XP-to-next so the UI can render a progress bar.
    from app.economy import xp_for_level
    cap = level_cap_for_stars(hero.stars)
    if hero.level < cap:
        xp_need = xp_for_level(hero.level)
        after = _project(hero, level=hero.level + 1)
        level_up = UpgradePreview(
            available=True,
            cost={
                "target_level": hero.level + 1,
                "level_cap": cap,
                "xp_current": hero.xp,
                "xp_needed": xp_need,
                "xp_remaining": max(0, xp_need - hero.xp),
            },
            delta=_delta(after, current),
            after=after,
        )
    else:
        level_up = UpgradePreview(
            available=False,
            cost={"target_level": hero.level, "level_cap": cap, "reason": "at level cap — ascend to raise"},
            delta={k: 0 for k in current},
            after=current,
        )

    # Star up — capped at MAX_STARS; needs `stars` fodder of same template.
    if hero.stars < MAX_STARS:
        from sqlalchemy import select as _sel
        owned_dupes = list(db.scalars(
            _sel(HeroInstance.id).where(
                HeroInstance.account_id == account.id,
                HeroInstance.template_id == hero.template_id,
                HeroInstance.id != hero.id,
            )
        ))
        needed = hero.stars
        after = _project(hero, stars=hero.stars + 1)
        star_up = UpgradePreview(
            available=len(owned_dupes) >= needed,
            cost={
                "target_stars": hero.stars + 1,
                "fodder_needed": needed,
                "fodder_available": len(owned_dupes),
            },
            delta=_delta(after, current),
            after=after,
        )
    else:
        star_up = UpgradePreview(
            available=False,
            cost={"target_stars": hero.stars, "reason": "max stars"},
            delta={k: 0 for k in current},
            after=current,
        )

    # Special up — flat boost; doesn't change stat sheet, but we surface
    # the next special-level number + scale multiplier so the UI can show
    # "your special hits +10% harder next level". Post shard-remap
    # (2026-05-12) availability gates on template-shard balance, not on
    # whether a fodder dupe exists.
    if hero.special_level < MAX_SPECIAL_LEVEL:
        from app.template_shards import shards_for_skill_up, get_shards
        shards_needed = shards_for_skill_up(hero.special_level) or 0
        shards_available = get_shards(account, hero.template.code)
        special_up = UpgradePreview(
            available=shards_needed > 0 and shards_available >= shards_needed,
            cost={
                "target_special_level": hero.special_level + 1,
                "shards_needed": shards_needed,
                "shards_available": shards_available,
                "max_special_level": MAX_SPECIAL_LEVEL,
                # +10% per level beyond 1 in the resolver.
                "scale_multiplier_after": round(1.0 + 0.10 * (hero.special_level + 1 - 1), 2),
            },
            # Stat sheet is unchanged by special-up; deltas are zero.
            delta={k: 0 for k in current},
            after=current,
        )
    else:
        special_up = UpgradePreview(
            available=False,
            cost={"target_special_level": hero.special_level, "reason": "max special level"},
            delta={k: 0 for k in current},
            after=current,
        )

    return HeroPreviewOut(
        hero_instance_id=hero.id,
        current=current,
        level_up=level_up,
        star_up=star_up,
        special_up=special_up,
    )


@router.get("/{hero_instance_id}/sell-preview", response_model=SellPreviewOut)
def sell_preview(
    hero_instance_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SellPreviewOut:
    """How much would I get for selling this hero? Read-only."""
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")
    coins, shards = _sell_value(hero)
    rarity = str(Rarity(hero.template.rarity) if not isinstance(hero.template.rarity, Rarity) else hero.template.rarity)
    return SellPreviewOut(
        hero_instance_id=hero.id, coins=coins, shards=shards,
        rarity=rarity, level=hero.level, stars=hero.stars,
    )


@router.post("/{hero_instance_id}/sell", response_model=SellOut, status_code=status.HTTP_201_CREATED)
def sell_hero(
    hero_instance_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SellOut:
    """Sell a hero for coins + shards. Auto-unequips gear; gear stays in
    inventory unattached (player can re-equip on someone else)."""
    hero = db.get(HeroInstance, hero_instance_id)
    if hero is None or hero.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hero not found")

    coins, shards = _sell_value(hero)

    # Auto-unequip any gear pinned to this hero so it doesn't get cascade-deleted.
    from app.models import Gear
    equipped = list(db.scalars(select(Gear).where(Gear.hero_instance_id == hero.id)))
    for g in equipped:
        g.hero_instance_id = None

    sold_id = hero.id
    db.delete(hero)
    account.coins += coins
    account.shards += shards
    db.commit()
    db.refresh(account)
    return SellOut(
        sold_hero_instance_id=sold_id,
        coins_granted=coins, shards_granted=shards,
        coins=account.coins, shards=account.shards,
    )
