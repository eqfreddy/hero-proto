"""Milestone rewards router.

Endpoints:
    GET  /stages/milestones                     — list all milestones + account state
    POST /stages/milestones/{milestone_id}/claim — claim an unlocked milestone
    POST /stages/milestones/legend-boss-summon  — spend 30 boss shards, get a hero
"""
from __future__ import annotations

import random
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.milestones import (
    claim_milestone,
    list_milestones,
    summon_legend_boss,
)
from app.models import Account
from app.routers.heroes import instance_out
from app.schemas import HeroInstanceOut, MilestoneClaimOut, MilestoneListOut, LegendBossSummonOut

router = APIRouter(prefix="/stages", tags=["milestones"])

DbDep = Annotated[Session, Depends(get_db)]
AccountDep = Annotated[Account, Depends(get_current_account)]


@router.get("/milestones", response_model=MilestoneListOut)
def get_milestones(account: AccountDep, db: DbDep):
    """Return all milestones with per-account claim state and progress."""
    return list_milestones(account, db)


# NOTE: The legend-boss-summon route MUST be registered before /{milestone_id}/claim
# so FastAPI does not try to match "legend-boss-summon" as an integer milestone_id.
@router.post("/milestones/legend-boss-summon", response_model=LegendBossSummonOut)
def legend_boss_summon(account: AccountDep, db: DbDep):
    """Spend 30 legend_boss_shards to pull one MYTH-tier boss hero."""
    hero = summon_legend_boss(account, db)
    return LegendBossSummonOut(
        hero=instance_out(hero),
        legend_boss_shards_balance=account.legend_boss_shards,
    )


@router.post("/milestones/{milestone_id}/claim", response_model=MilestoneClaimOut)
def claim(milestone_id: int, account: AccountDep, db: DbDep):
    """Claim an unlocked, unclaimed milestone. 409 if already claimed or locked."""
    result = claim_milestone(account, milestone_id, db, rng=random.Random())
    return MilestoneClaimOut(**result)
