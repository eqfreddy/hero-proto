"""Milestone reward service.

Milestone rewards unlock every N cleared stages and grant:
  - A guaranteed quantity of generic shards (credited to account.shards).
  - A non-deterministic chance at one legend_boss_shard (with a pity floor).

Players accumulate legend_boss_shards until they reach LEGEND_BOSS_SUMMON_COST,
then spend them via the legend-boss summon endpoint to pull a MYTH-tier boss hero.

See docs/milestone-rewards-spec-2026-05-13.md for the full spec.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.economy import load_cleared
from app.models import (
    Account,
    AccountMilestoneClaim,
    HeroInstance,
    HeroTemplate,
    Rarity,
    StageMilestone,
    utcnow,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEGEND_PITY_FLOOR: int = 10        # consecutive non-award claims before guarantee
LEGEND_BOSS_SUMMON_COST: int = 30  # legend_boss_shards required for one summon


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stages_cleared_count(account: Account) -> int:
    return len(load_cleared(account))


def _load_all_milestones(db: Session) -> list[StageMilestone]:
    return list(db.scalars(
        select(StageMilestone).order_by(StageMilestone.stage_count)
    ))


def _claimed_ids(account: Account, db: Session) -> set[int]:
    rows = db.scalars(
        select(AccountMilestoneClaim.milestone_id)
        .where(AccountMilestoneClaim.account_id == account.id)
    )
    return set(rows)


# ---------------------------------------------------------------------------
# Pity / legend-shard roll
# ---------------------------------------------------------------------------


def roll_legend_shard(
    account: Account,
    base_chance: float,
    rng: random.Random,
) -> int:
    """Roll for one legend_boss_shard.  Returns 1 on award, 0 on miss.
    Mutates account.milestone_legend_pity in-place; caller must commit.
    """
    pity = account.milestone_legend_pity
    if pity >= LEGEND_PITY_FLOOR:
        account.milestone_legend_pity = 0
        return 1
    if rng.random() < base_chance:
        account.milestone_legend_pity = 0
        return 1
    account.milestone_legend_pity = pity + 1
    return 0


# ---------------------------------------------------------------------------
# Public API used by the router + battle hook
# ---------------------------------------------------------------------------


def check_milestone_unlocks(account: Account, db: Session) -> list[int]:
    """Return milestone IDs that are now unlocked but NOT yet claimed.
    Pure read — no state mutation. Safe to call after every stage clear.
    """
    cleared = _stages_cleared_count(account)
    if cleared == 0:
        return []
    claimed = _claimed_ids(account, db)
    result: list[int] = []
    for ms in _load_all_milestones(db):
        if ms.stage_count <= cleared and ms.id not in claimed:
            result.append(ms.id)
    return result


def get_next_milestone(
    milestones: list[StageMilestone],
    cleared: int,
    claimed: set[int],
) -> StageMilestone | None:
    """Return the next milestone for the Zeigarnik progress counter.

    Priority:
    1. The first milestone that is NOT yet unlocked (stage_count > cleared) —
       this drives the "X stages to next milestone" counter.
    2. If all milestones are cleared, return None.

    Milestones already unlocked but unclaimed are surfaced via
    check_milestone_unlocks(); the progress counter specifically focuses
    on what the player is working toward, not what they forgot to collect.
    """
    for ms in milestones:
        if ms.stage_count > cleared:
            return ms
    return None


def list_milestones(account: Account, db: Session) -> dict:
    """Build the full GET /stages/milestones response payload."""
    cleared = _stages_cleared_count(account)
    claimed_set = _claimed_ids(account, db)
    all_ms = _load_all_milestones(db)

    # Fetch all claim records for this account in one query.
    claim_rows: dict[int, AccountMilestoneClaim] = {}
    for row in db.scalars(
        select(AccountMilestoneClaim).where(
            AccountMilestoneClaim.account_id == account.id
        )
    ):
        claim_rows[row.milestone_id] = row

    milestones_out = []
    for ms in all_ms:
        claim = claim_rows.get(ms.id)
        milestones_out.append({
            "id": ms.id,
            "stage_count": ms.stage_count,
            "template_shards": ms.template_shards,
            "legend_shard_chance": ms.legend_shard_chance,
            "label": ms.label,
            "unlocked": cleared >= ms.stage_count,
            "claimed": claim is not None,
            "claimed_at": claim.claimed_at.isoformat() + "Z" if claim else None,
            "legend_shards_granted": claim.legend_shards_granted if claim else None,
        })

    next_ms = get_next_milestone(all_ms, cleared, claimed_set)
    next_milestone_out: dict | None = None
    if next_ms is not None:
        stages_to_go = max(0, next_ms.stage_count - cleared)
        next_milestone_out = {
            "id": next_ms.id,
            "stage_count": next_ms.stage_count,
            "stages_to_go": stages_to_go,
            "template_shards": next_ms.template_shards,
            "legend_shard_chance": next_ms.legend_shard_chance,
            "label": next_ms.label,
        }

    return {
        "stages_cleared_count": cleared,
        "next_milestone": next_milestone_out,
        "milestones": milestones_out,
        "legend_boss_shards": account.legend_boss_shards,
        "legend_summon_cost": LEGEND_BOSS_SUMMON_COST,
        "pity_counter": account.milestone_legend_pity,
        "pity_floor": LEGEND_PITY_FLOOR,
    }


def claim_milestone(
    account: Account,
    milestone_id: int,
    db: Session,
    rng: random.Random | None = None,
) -> dict:
    """Claim an unlocked, unclaimed milestone.

    Raises HTTP 404 if the milestone does not exist.
    Raises HTTP 409 if the milestone is not yet unlocked or already claimed.
    Returns the claim result dict on success.
    """
    if rng is None:
        rng = random.Random()

    ms = db.get(StageMilestone, milestone_id)
    if ms is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="milestone not found")

    cleared = _stages_cleared_count(account)
    if cleared < ms.stage_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="milestone not yet unlocked",
        )

    # Check existing claim (pre-DB soft-check; DB UNIQUE is the backstop).
    existing = db.scalar(
        select(AccountMilestoneClaim).where(
            AccountMilestoneClaim.account_id == account.id,
            AccountMilestoneClaim.milestone_id == milestone_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already claimed",
        )

    # Roll legend shard — mutates account.milestone_legend_pity.
    legend_granted = roll_legend_shard(account, ms.legend_shard_chance, rng)

    # Credit generic shards (account.shards is the cross-template scalar).
    account.shards = (account.shards or 0) + ms.template_shards

    # Credit legend boss shards.
    account.legend_boss_shards = (account.legend_boss_shards or 0) + legend_granted

    # Record the claim.
    claim = AccountMilestoneClaim(
        account_id=account.id,
        milestone_id=milestone_id,
        claimed_at=utcnow(),
        template_shards_granted=ms.template_shards,
        legend_shards_granted=legend_granted,
    )
    db.add(claim)

    try:
        db.flush()  # surface IntegrityError before commit if race condition
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already claimed",
        )

    db.commit()

    return {
        "milestone_id": milestone_id,
        "template_shards_granted": ms.template_shards,
        "legend_shards_granted": legend_granted,
        "legend_boss_shards_balance": account.legend_boss_shards,
        "pity_counter": account.milestone_legend_pity,
    }


def summon_legend_boss(account: Account, db: Session) -> HeroInstance:
    """Spend LEGEND_BOSS_SUMMON_COST legend_boss_shards to pull one hero
    from the MYTH-rarity boss pool.

    Raises HTTP 409 if insufficient shards.
    Raises HTTP 404 if the boss pool is empty.
    Returns the newly created HeroInstance.
    """
    if (account.legend_boss_shards or 0) < LEGEND_BOSS_SUMMON_COST:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"insufficient legend boss shards "
                f"(have {account.legend_boss_shards}, need {LEGEND_BOSS_SUMMON_COST})"
            ),
        )

    pool = list(db.scalars(
        select(HeroTemplate).where(
            HeroTemplate.rarity == Rarity.MYTH,
            HeroTemplate.is_legend_boss_pool.is_(True),
        )
    ))
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="legend boss pool is empty — contact support",
        )

    rng = random.Random()
    template = rng.choice(pool)

    # Deduct cost.
    account.legend_boss_shards -= LEGEND_BOSS_SUMMON_COST

    # Check for existing instance (duplicate → shard credit, matching gacha flow).
    existing = db.scalar(
        select(HeroInstance).where(
            HeroInstance.account_id == account.id,
            HeroInstance.template_id == template.id,
        )
    )
    if existing is not None:
        # Grant dupe shards the same way gacha does.
        from app.template_shards import grant_dupe_shards
        grant_dupe_shards(account, template.code, Rarity(template.rarity))
        db.commit()
        return existing

    hero = HeroInstance(
        account_id=account.id,
        template_id=template.id,
        level=1,
        xp=0,
        stars=1,
    )
    db.add(hero)
    db.commit()
    db.refresh(hero)
    return hero
