from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.daily_bonus import (
    DailyReward,
    apply_claim,
    can_claim,
    preview_next_streak,
    reward_for_streak,
)
from app.db import get_db
from app.deps import get_current_account
from app.economy import compute_energy, load_cleared
from app.models import Account, Battle, Guild, GuildMember, GuildRole, HeroInstance
from app.schemas import MeOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut)
def get_me(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> MeOut:
    cleared = load_cleared(account)
    has_summoned = db.query(HeroInstance).filter_by(account_id=account.id).limit(1).first() is not None
    has_battled = db.query(Battle).filter_by(account_id=account.id).limit(1).first() is not None
    return MeOut(
        id=account.id,
        email=account.email,
        gems=account.gems,
        coins=account.coins,
        shards=account.shards,
        access_cards=account.access_cards,
        free_summon_credits=account.free_summon_credits or 0,
        energy=compute_energy(account),
        energy_cap=settings.energy_cap,
        pulls_since_epic=account.pulls_since_epic,
        stages_cleared=sorted(cleared),
        tutorial_cleared="tutorial_first_ticket" in cleared,
        has_summoned=has_summoned,
        has_battled=has_battled,
    )


class DeleteMeIn(BaseModel):
    confirm_email: EmailStr


@router.delete("", response_model=dict)
def delete_me(
    body: DeleteMeIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Irreversibly delete the caller's account and all related data (GDPR art. 17)."""
    if body.confirm_email.lower() != account.email.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm_email must match your account")

    # If this user is a guild leader, promote or disband cleanly before the cascade fires.
    membership = db.get(GuildMember, account.id)
    if membership is not None and membership.role == GuildRole.LEADER:
        from sqlalchemy import select

        successor = db.scalar(
            select(GuildMember)
            .where(
                GuildMember.guild_id == membership.guild_id,
                GuildMember.account_id != account.id,
            )
            .order_by(GuildMember.joined_at)
        )
        if successor is not None:
            successor.role = GuildRole.LEADER
        else:
            # Last member leaving — disband the guild so it doesn't orphan.
            g = db.get(Guild, membership.guild_id)
            if g is not None:
                db.delete(g)

    account_id = account.id
    account_email = account.email
    db.delete(account)
    db.commit()
    return {"deleted_account_id": account_id, "deleted_email": account_email}


# --- Daily login bonus -------------------------------------------------------


class DailyBonusRewardOut(BaseModel):
    coins: int = 0
    gems: int = 0
    shards: int = 0
    access_cards: int = 0


class DailyBonusStatusOut(BaseModel):
    current_streak: int
    next_streak_if_claimed: int
    can_claim: bool
    next_claim_at: datetime | None
    today_reward: DailyBonusRewardOut
    last_claim_at: datetime | None


class DailyBonusClaimOut(BaseModel):
    granted: DailyBonusRewardOut
    streak_after: int
    next_claim_at: datetime
    was_reset: bool


def _reward_schema(r: DailyReward) -> DailyBonusRewardOut:
    return DailyBonusRewardOut(
        coins=r.coins, gems=r.gems, shards=r.shards, access_cards=r.access_cards,
    )


@router.get("/daily-bonus", response_model=DailyBonusStatusOut)
def daily_bonus_status(
    account: Annotated[Account, Depends(get_current_account)],
) -> DailyBonusStatusOut:
    available, next_at = can_claim(account)
    next_streak = preview_next_streak(account)
    today = reward_for_streak(next_streak)
    return DailyBonusStatusOut(
        current_streak=account.daily_streak,
        next_streak_if_claimed=next_streak,
        can_claim=available,
        next_claim_at=next_at,
        today_reward=_reward_schema(today),
        last_claim_at=account.last_daily_claim_at,
    )


@router.post("/daily-bonus/claim", response_model=DailyBonusClaimOut, status_code=status.HTTP_201_CREATED)
def daily_bonus_claim(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> DailyBonusClaimOut:
    available, next_at = can_claim(account)
    if not available:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"daily bonus not yet available — next claim at {next_at.isoformat() if next_at else 'unknown'}",
        )
    result = apply_claim(account)
    db.commit()
    return DailyBonusClaimOut(
        granted=_reward_schema(result.granted),
        streak_after=result.streak_after,
        next_claim_at=result.next_claim_at,
        was_reset=result.was_reset,
    )


# --- Energy refill (gem sink) ------------------------------------------------


class EnergyRefillOut(BaseModel):
    gems_spent: int
    refills_today: int
    refills_remaining_today: int
    energy: int


@router.post("/energy/refill", response_model=EnergyRefillOut, status_code=status.HTTP_201_CREATED)
def refill_energy(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> EnergyRefillOut:
    """Instantly fill energy to cap in exchange for gems. Capped at
    settings.energy_refill_max_per_day per UTC day."""
    from app.daily import day_key, on_gems_spent

    today = day_key()
    # Reset the per-day counter if it's a new day.
    if account.refills_today_key != today:
        account.refills_today_key = today
        account.refills_today_count = 0

    if account.refills_today_count >= settings.energy_refill_max_per_day:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"daily refill limit reached ({settings.energy_refill_max_per_day})",
        )

    cost = settings.energy_refill_cost_gems
    if account.gems < cost:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough gems (need {cost}, have {account.gems})",
        )

    current = compute_energy(account)
    if current >= settings.energy_cap:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "energy is already at cap — no refill needed",
        )

    account.gems -= cost
    account.energy_stored = settings.energy_cap
    account.energy_last_tick_at = utcnow_for_model()
    account.refills_today_count += 1

    # Daily-quest hook: SPEND_GEMS progress.
    on_gems_spent(db, account, cost)

    db.commit()
    db.refresh(account)
    return EnergyRefillOut(
        gems_spent=cost,
        refills_today=account.refills_today_count,
        refills_remaining_today=settings.energy_refill_max_per_day - account.refills_today_count,
        energy=compute_energy(account),
    )


def utcnow_for_model():
    """Indirection so tests can patch the clock if needed without stepping on utcnow globally."""
    from app.models import utcnow
    return utcnow()
