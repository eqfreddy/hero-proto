import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.daily import on_summon
from app.event_state import QUEST_KINDS_SUMMON, on_activity as event_on_activity
from app.db import get_db
from app.deps import get_current_account
from app.gacha import roll, roll_variance, serialize_variance
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


def _do_one_pull(db: Session, account: Account, rng: random.Random, *, allow_free: bool = True) -> SummonOut:
    """Perform one summon. Consumes free_summon_credits before shards — so a
    tutorial reward or starter-pack grant lets players pull without spending.
    Pity counter + rarity roll are identical either way.

    allow_free=False forces shard payment even if credits available (used by
    x10 which is a single transaction: either all shards or all credits, no
    mixing).
    """
    paid_with_credit = allow_free and (account.free_summon_credits or 0) > 0
    if paid_with_credit:
        account.free_summon_credits = (account.free_summon_credits or 0) - 1
    else:
        if account.shards < 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "not enough shards")
        account.shards -= 1
    result = roll(account.pulls_since_epic, rng)
    template = _pick_template(db, result.rarity, rng)
    account.pulls_since_epic = result.new_pity

    # Phase 2.2 — duplicate detection. If the account already owns ≥1 copy of
    # this template, roll per-stat variance so this copy isn't identical.
    # First copy stays vanilla (variance_pct_json = "{}"). Variance is set at
    # creation and never re-rolled — keeps the stat sheet stable across
    # ascensions and sells.
    already_owned = db.scalar(
        select(HeroInstance.id)
        .where(
            HeroInstance.account_id == account.id,
            HeroInstance.template_id == template.id,
        )
        .limit(1)
    )
    variance_blob = "{}"
    if already_owned is not None:
        variance_blob = serialize_variance(roll_variance(rng))

    hero = HeroInstance(
        account_id=account.id, template_id=template.id, level=1, xp=0,
        variance_pct_json=variance_blob,
    )
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
    event_on_activity(db, account, "summon_pull", quest_kinds=QUEST_KINDS_SUMMON)
    from app.achievements import check_achievements as _ca
    _ca(db, account)
    from app.account_level import XP_PER_SUMMON_PULL, grant_xp as _gxp
    _gxp(db, account, XP_PER_SUMMON_PULL)
    db.commit()
    from app.analytics import track as _track
    _track("summon_x1", account.id, {
        "rarity": str(out.rarity),
        "epic_pity_triggered": out.pulled_epic_pity,
    })
    return out


@router.post("/x10", response_model=list[SummonOut], status_code=status.HTTP_201_CREATED)
def summon_ten(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SummonOut]:
    if account.shards < 10:
        raise HTTPException(status.HTTP_409_CONFLICT, "not enough shards (need 10)")
    rng = random.Random()
    # x10 is always a shard purchase — free credits apply to /x1 only to keep
    # the reward semantics clean (one credit = one pull).
    out = [_do_one_pull(db, account, rng, allow_free=False) for _ in range(10)]
    on_summon(db, account, 10)
    event_on_activity(db, account, "summon_pull", amount=10, quest_kinds=QUEST_KINDS_SUMMON)
    from app.achievements import check_achievements as _ca
    _ca(db, account)
    from app.account_level import XP_PER_SUMMON_PULL, grant_xp as _gxp
    _gxp(db, account, XP_PER_SUMMON_PULL * 10)
    db.commit()
    from app.analytics import track as _track
    rarities = {r: 0 for r in ("COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTH")}
    for s in out:
        rarities[str(s.rarity)] = rarities.get(str(s.rarity), 0) + 1
    best = max(out, key=lambda s: ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTH"].index(str(s.rarity)))
    _track("summon_x10", account.id, {
        "best_rarity": str(best.rarity),
        "rarity_counts": rarities,
        "epic_pity_triggered": any(s.pulled_epic_pity for s in out),
    })
    return out


# --- Event-banner summon (Phase 2.2) ----------------------------------------
#
# Limited-time path that lets players pull a single specified hero (typically
# Myth-tier) outside the standard pool. Gated strictly on an active
# LiveOpsEvent of kind EVENT_BANNER. Per-account pull cap stored on
# Account.event_state_json so the cap survives across sessions.
#
# Cost is paid in shards (default 5 per pull). No pity, no rarity roll —
# every pull lands the configured hero. This is intentional: event banners
# are guaranteed-grant, not probabilistic, so the LiveOps tone stays
# generous rather than gacha-y.


import json as _json


def _event_banner_pulls(account: Account, banner_id: int) -> int:
    try:
        state = _json.loads(account.event_state_json or "{}")
    except _json.JSONDecodeError:
        return 0
    if not isinstance(state, dict):
        return 0
    return int((state.get("event_banner_pulls") or {}).get(str(banner_id), 0) or 0)


def _bump_event_banner_pulls(account: Account, banner_id: int) -> int:
    try:
        state = _json.loads(account.event_state_json or "{}")
    except _json.JSONDecodeError:
        state = {}
    if not isinstance(state, dict):
        state = {}
    pulls = state.setdefault("event_banner_pulls", {})
    if not isinstance(pulls, dict):
        pulls = {}
        state["event_banner_pulls"] = pulls
    new_count = int(pulls.get(str(banner_id), 0) or 0) + 1
    pulls[str(banner_id)] = new_count
    account.event_state_json = _json.dumps(state, separators=(",", ":"))
    return new_count


@router.get("/event-banner")
def event_banner_status(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Returns the active event-banner config + this account's pull
    count + remaining caps. Empty dict when no banner is active so
    the UI can hide the panel cleanly."""
    from app.liveops import active_event_banner, event_banner_payload

    banner = active_event_banner(db)
    if banner is None:
        return {"active": False}
    payload = event_banner_payload(banner)
    template = db.scalar(
        select(HeroTemplate).where(HeroTemplate.code == payload["hero_template_code"])
    )
    pulls = _event_banner_pulls(account, banner.id)
    return {
        "active": True,
        "banner_id": banner.id,
        "banner_name": banner.name,
        "ends_at": banner.ends_at.isoformat() + "Z" if banner.ends_at else None,
        "hero_template_code": payload["hero_template_code"],
        "hero_template_name": template.name if template is not None else None,
        "hero_rarity": str(template.rarity) if template is not None else None,
        "shard_cost": payload["shard_cost"],
        "per_account_cap": payload["per_account_cap"],
        "pulls_used": pulls,
        "pulls_remaining": max(0, payload["per_account_cap"] - pulls),
    }


@router.post("/event-banner", response_model=SummonOut, status_code=status.HTTP_201_CREATED)
def summon_event_banner(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SummonOut:
    """Single pull on the active event banner. 409 if no banner is active,
    if the per-account cap is reached, or if shard balance is insufficient.

    Guarantees the hero — no rarity roll. Returns a SummonOut with
    pulled_epic_pity=False (event banners don't interact with pity)."""
    from app.liveops import active_event_banner, event_banner_payload
    from app.routers.heroes import instance_out as _instance_out

    banner = active_event_banner(db)
    if banner is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no event banner is active")
    payload = event_banner_payload(banner)
    if not payload["hero_template_code"]:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "event banner is misconfigured (missing hero_template_code)",
        )

    pulls_used = _event_banner_pulls(account, banner.id)
    if pulls_used >= payload["per_account_cap"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"event banner cap reached ({payload['per_account_cap']} pulls)",
        )

    if account.shards < payload["shard_cost"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough shards (need {payload['shard_cost']})",
        )

    template = db.scalar(
        select(HeroTemplate).where(HeroTemplate.code == payload["hero_template_code"])
    )
    if template is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"event hero template {payload['hero_template_code']!r} not seeded",
        )

    account.shards -= payload["shard_cost"]

    # Variance applies if this is a duplicate (player already owns Applecrumb).
    rng = random.Random()
    already_owned = db.scalar(
        select(HeroInstance.id)
        .where(
            HeroInstance.account_id == account.id,
            HeroInstance.template_id == template.id,
        )
        .limit(1)
    )
    variance_blob = "{}"
    if already_owned is not None:
        variance_blob = serialize_variance(roll_variance(rng))

    hero = HeroInstance(
        account_id=account.id, template_id=template.id, level=1, xp=0,
        variance_pct_json=variance_blob,
    )
    db.add(hero)
    db.add(GachaRecord(
        account_id=account.id,
        template_id=template.id,
        rarity=template.rarity,
        pity_before=account.pulls_since_epic,
    ))
    _bump_event_banner_pulls(account, banner.id)

    db.flush()
    _ = hero.template

    on_summon(db, account, 1)
    event_on_activity(db, account, "summon_pull", quest_kinds=QUEST_KINDS_SUMMON)
    from app.account_level import XP_PER_SUMMON_PULL, grant_xp as _gxp
    _gxp(db, account, XP_PER_SUMMON_PULL)
    db.commit()

    from app.analytics import track as _track
    _track("summon_event_banner", account.id, {
        "banner_id": banner.id,
        "banner_name": banner.name,
        "hero_template_code": payload["hero_template_code"],
        "rarity": str(template.rarity),
    })

    out = SummonOut(
        hero=_instance_out(hero),
        rarity=Rarity(template.rarity) if not isinstance(template.rarity, Rarity) else template.rarity,
        pulled_epic_pity=False,
        pulls_since_epic_after=account.pulls_since_epic,
    )
    return out
