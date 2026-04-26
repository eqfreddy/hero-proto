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
from app.deps import enforce_data_export_rate_limit, get_current_account
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
    from app.account_level import xp_to_next as _xp_to_next
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
        account_level=account.account_level or 1,
        account_xp=account.account_xp or 0,
        account_xp_to_next=_xp_to_next(account.account_level or 1),
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
    from app.account_level import XP_PER_DAILY_BONUS, grant_xp as _gxp
    _gxp(db, account, XP_PER_DAILY_BONUS)
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


# --- Team presets + last-team helper ----------------------------------------


import json as _json
from sqlalchemy import select as _select, desc as _desc
from sqlalchemy.exc import IntegrityError as _IntegrityError

from app.models import (
    Battle as _Battle,
    HeroInstance as _HeroInstance,
    TeamPreset as _TeamPreset,
)
from app.schemas import LastTeamOut, TeamPresetIn, TeamPresetOut


MAX_TEAM_PRESETS = 5


def _preset_out(p: _TeamPreset) -> TeamPresetOut:
    try:
        team = _json.loads(p.hero_ids_json or "[]")
    except _json.JSONDecodeError:
        team = []
    return TeamPresetOut(
        id=p.id, name=p.name, team=team,
        created_at=p.created_at, updated_at=p.updated_at,
    )


def _validate_team(db: Session, account: Account, ids: list[int]) -> list[int]:
    """Strip non-owned hero ids. Used by preset read/write so a stale preset
    (hero sold / fed as ascension fodder) silently becomes a short preset
    rather than exploding on battle POST.
    """
    owned = {
        h.id for h in db.scalars(
            _select(_HeroInstance).where(
                _HeroInstance.account_id == account.id,
                _HeroInstance.id.in_(ids),
            )
        )
    }
    return [i for i in ids if i in owned]


@router.get("/team-presets", response_model=list[TeamPresetOut])
def list_team_presets(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TeamPresetOut]:
    rows = db.scalars(
        _select(_TeamPreset)
        .where(_TeamPreset.account_id == account.id)
        .order_by(_TeamPreset.updated_at.desc())
    )
    return [_preset_out(p) for p in rows]


@router.post("/team-presets", response_model=TeamPresetOut, status_code=status.HTTP_201_CREATED)
def upsert_team_preset(
    body: TeamPresetIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> TeamPresetOut:
    """Create or update a preset by name. Idempotent — posting the same name
    twice overwrites the team. Cap MAX_TEAM_PRESETS distinct names per account.
    """
    clean = _validate_team(db, account, body.team)
    if not clean:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "preset must include at least one owned hero",
        )

    existing = db.scalar(
        _select(_TeamPreset).where(
            _TeamPreset.account_id == account.id,
            _TeamPreset.name == body.name.strip(),
        )
    )
    if existing is not None:
        existing.hero_ids_json = _json.dumps(clean)
        existing.updated_at = utcnow_for_model()
        db.commit()
        db.refresh(existing)
        return _preset_out(existing)

    count = db.scalar(
        _select(_TeamPreset).where(_TeamPreset.account_id == account.id)
    )  # at-least-one check via scalar (quick)
    current = db.query(_TeamPreset).filter_by(account_id=account.id).count()
    if current >= MAX_TEAM_PRESETS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"max {MAX_TEAM_PRESETS} presets per account — delete one first",
        )

    preset = _TeamPreset(
        account_id=account.id,
        name=body.name.strip(),
        hero_ids_json=_json.dumps(clean),
    )
    db.add(preset)
    try:
        db.commit()
    except _IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "preset name already taken")
    db.refresh(preset)
    return _preset_out(preset)


@router.delete("/team-presets/{preset_id}", response_model=dict)
def delete_team_preset(
    preset_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    p = db.get(_TeamPreset, preset_id)
    if p is None or p.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "preset not found")
    db.delete(p)
    db.commit()
    return {"deleted_preset_id": preset_id}


@router.get("/last-team", response_model=LastTeamOut)
def last_team(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> LastTeamOut:
    """Return the team from the player's most recent successful battle.

    Drives the "Use last team" one-click on the Battle/Arena/Raid tabs.
    Filters out any hero ids that are no longer owned (ascended away, etc.).
    Falls back to empty if no history yet.
    """
    b = db.scalar(
        _select(_Battle)
        .where(_Battle.account_id == account.id)
        .order_by(_desc(_Battle.id))
        .limit(1)
    )
    if b is None:
        return LastTeamOut(team=[], source="empty")
    try:
        raw = _json.loads(b.team_json or "[]")
    except _json.JSONDecodeError:
        raw = []
    clean = _validate_team(db, account, [int(x) for x in raw if isinstance(x, int) or (isinstance(x, str) and x.isdigit())])
    return LastTeamOut(team=clean, source="battle")


# --- Active sessions / login history ----------------------------------------
#
# Each live RefreshToken row IS a session: a credential issued at some point
# from some IP/UA, still good until expired or revoked. We expose them so the
# user can see "where am I logged in" and revoke individual sessions (lost
# laptop, shared computer) or all of them at once.

from app.models import RefreshToken as _RefreshToken, utcnow as _utcnow


class SessionOut(BaseModel):
    id: int
    issued_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    ip: str | None = None
    user_agent: str | None = None
    is_current: bool = False


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SessionOut]:
    """All live refresh tokens for the account, newest-first. Revoked, expired,
    and rotated-out tokens are excluded — they're not real sessions anymore.

    `is_current` is heuristic: we don't know the caller's refresh-token id from
    the access token alone, so we mark the session with the most recent
    activity (`last_used_at`, falling back to `issued_at`). For the common
    flow — caller just logged in or rotated, then asked for sessions — that's
    their session. Wrong only if a *different* device authed more recently."""
    now = _utcnow()
    rows = list(db.scalars(
        _select(_RefreshToken)
        .where(
            _RefreshToken.account_id == account.id,
            _RefreshToken.revoked_at.is_(None),
            _RefreshToken.replaced_by_id.is_(None),
            _RefreshToken.expires_at > now,
        )
        .order_by(_desc(_RefreshToken.id))
    ))
    current_id: int | None = None
    if rows:
        current_id = max(rows, key=lambda r: (r.last_used_at or r.issued_at, r.id)).id
    return [
        SessionOut(
            id=r.id,
            issued_at=r.issued_at,
            expires_at=r.expires_at,
            last_used_at=r.last_used_at,
            ip=r.created_ip,
            user_agent=r.user_agent,
            is_current=(r.id == current_id),
        )
        for r in rows
    ]


@router.post("/sessions/{session_id}/revoke", response_model=dict)
def revoke_session(
    session_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Kill one specific session. Other sessions (and the access token that
    made *this* call) keep working — only the targeted refresh chain dies."""
    row = db.get(_RefreshToken, session_id)
    if row is None or row.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    if row.revoked_at is None:
        row.revoked_at = _utcnow()
        db.commit()
    return {"revoked": True, "id": session_id}


@router.post("/sessions/revoke-all", response_model=dict)
def revoke_all_sessions(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Logout-everywhere: revokes all live refresh tokens AND bumps token_version
    so any in-flight access tokens (including the one that called this) die.
    Caller will need to re-login on every device, here included."""
    now = _utcnow()
    revoked = 0
    for row in db.scalars(
        _select(_RefreshToken).where(
            _RefreshToken.account_id == account.id,
            _RefreshToken.revoked_at.is_(None),
        )
    ):
        row.revoked_at = now
        revoked += 1
    account.token_version = (account.token_version or 0) + 1
    db.commit()
    return {"revoked": revoked}


# --- GDPR data export -------------------------------------------------------


@router.get("/export")
def export_account_data(
    account: Annotated[Account, Depends(enforce_data_export_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """GDPR art. 20 — return everything the system holds about this account
    as a single JSON blob. Sensitive material (password hash, TOTP secret,
    raw refresh tokens) is redacted; per-table caps prevent unbounded blobs.

    Rate-limited to 1/min/account: legitimate users hit this maybe once a
    year, never repeatedly, and the query is expensive (multi-table join,
    multi-MB response). The cap protects DB time even from authenticated
    callers with stolen access tokens."""
    from app.data_export import export_account as _export
    return _export(db, account)
