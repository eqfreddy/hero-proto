"""Friend Points endpoints + friend-summon banner.

GET  /friend-points                — balance + send-cap status + pity
POST /friend-points/ping/{id}      — daily ping → +5 FP both sides
POST /friend-points/summon         — spend 50 FP for one friend-banner pull
"""
from __future__ import annotations

import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import friend_points as fp_service
from app.db import get_db
from app.deps import get_current_account
from app.models import (
    Account, GachaRecord, HeroInstance, HeroTemplate, Rarity,
)
from app.routers.heroes import instance_out
from app.routers.summon import _pick_template
from app.gacha import roll_variance, serialize_variance
from app.schemas import HeroInstanceOut, SummonOut

router = APIRouter(prefix="/friend-points", tags=["friend-points"])


@router.get("")
def get_status(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return fp_service.status(db, account)


@router.post("/ping/{friend_id}", status_code=status.HTTP_201_CREATED)
def ping_friend(
    friend_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    res = fp_service.send_ping(db, account, friend_id)
    if not res.sent:
        raise HTTPException(status.HTTP_409_CONFLICT, res.reason or "ping rejected")
    db.commit()
    return {
        "sent": True,
        "fp_granted": res.fp_granted_to_self,
        "fp_recipient_granted": res.fp_granted_to_recipient,
        "balance": int(account.friend_points or 0),
    }


@router.post("/summon", response_model=SummonOut, status_code=status.HTTP_201_CREATED)
def summon_friend_banner(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SummonOut:
    if not fp_service.can_afford_summon(account):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"need {fp_service.FP_PER_SUMMON} Friend Points",
        )
    rng = random.Random()
    pity = int(account.fp_pulls_since_epic or 0)
    result = fp_service.fp_roll(pity, rng)
    template = _pick_template(db, result.rarity, rng)

    account.friend_points = int(account.friend_points or 0) - fp_service.FP_PER_SUMMON
    account.fp_pulls_since_epic = result.new_pity

    # Shard-remap (2026-05-12): friend-points dupe pulls credit shards
    # only; no second HeroInstance row.
    existing = db.scalar(
        select(HeroInstance).where(
            HeroInstance.account_id == account.id,
            HeroInstance.template_id == template.id,
        ).limit(1)
    )
    db.add(GachaRecord(
        account_id=account.id,
        template_id=template.id,
        rarity=result.rarity,
        pity_before=pity,
    ))
    is_dupe = existing is not None
    shards_granted = 0
    if is_dupe:
        from app.template_shards import grant_dupe_shards, SHARDS_ON_DUPE
        grant_dupe_shards(account, template.code, template.rarity)
        shards_granted = SHARDS_ON_DUPE.get(template.rarity, 0)
        hero = existing
    else:
        hero = HeroInstance(
            account_id=account.id, template_id=template.id, level=1, xp=0,
            variance_pct_json="{}",
        )
        db.add(hero)
    db.flush()
    _ = hero.template
    db.commit()

    return SummonOut(
        hero=instance_out(hero),
        rarity=result.rarity,
        pulled_epic_pity=result.pity_triggered,
        pulls_since_epic_after=account.fp_pulls_since_epic,
        is_duplicate=is_dupe,
        shards_granted=shards_granted,
    )
