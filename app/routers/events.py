"""Active-event surface: read player progress + claim rewards.

  GET  /events/active                       active spec, balance, quest progress, milestones
  POST /events/quests/{code}/claim          mark quest claimed, grant currency reward
  POST /events/milestones/{idx}/redeem      spend currency, grant milestone contents

All endpoints 404 cleanly when no event is active. Quest + milestone
definitions come from the JSON spec on disk; per-account state lives in
Account.event_state_json.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.event_state import (
    EventSpec,
    active_event_spec,
    claim_quest,
    currency_balance,
    grant_currency,
    is_claimed,
    quest_progress,
    redeem_milestone,
    redeemed_milestones,
    spend_currency,
)
from app.models import Account, HeroInstance, HeroTemplate, LiveOpsEvent, utcnow
from app.store import GRANTABLE_CURRENCIES

router = APIRouter(prefix="/events", tags=["events"])


def _require_active_event() -> EventSpec:
    spec = active_event_spec()
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no event active")
    return spec


def _grant_milestone(
    db: Session, account: Account, contents: dict,
) -> dict:
    """Apply a milestone's `contents` dict to the account. Mirrors
    store.apply_grant but doesn't write to the PurchaseLedger (event
    rewards are off-ledger; refund flows don't need them).
    """
    granted: dict = {}
    for kind in GRANTABLE_CURRENCIES:
        amount = int(contents.get(kind, 0) or 0)
        if amount <= 0:
            continue
        setattr(account, kind, getattr(account, kind) + amount)
        granted[kind] = amount

    free_summons = int(contents.get("free_summon_credits", 0) or 0)
    if free_summons > 0:
        account.free_summon_credits = (account.free_summon_credits or 0) + free_summons
        granted["free_summon_credits"] = free_summons

    code = contents.get("hero_template_code")
    if code:
        tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
        if tmpl is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"milestone references missing hero template {code!r}",
            )
        hero = HeroInstance(account_id=account.id, template_id=tmpl.id)
        db.add(hero)
        db.flush()
        granted["hero_instance_id"] = hero.id
        granted["hero_name"] = tmpl.name
    return granted


@router.get("/active")
def get_active_event(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Returns the active event spec joined with the caller's progress.
    404 when no event window is currently live.
    """
    spec = active_event_spec()
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no event active")

    # Spec may be live by date but not yet activated by ops (no LiveOpsEvent
    # row). In that case the activity hooks won't drop currency, so report
    # this honestly to the client.
    has_live_row = db.scalar(
        select(LiveOpsEvent).where(
            LiveOpsEvent.starts_at <= utcnow(),
            LiveOpsEvent.ends_at > utcnow(),
        )
    ) is not None

    balance = currency_balance(account, spec.id)

    quests = []
    for q in spec.quests:
        progress = quest_progress(account, spec.id, q["code"])
        goal = int(q.get("goal", 1))
        quests.append({
            "code": q["code"],
            "title": q.get("title", q["code"]),
            "kind": q.get("kind", ""),
            "goal": goal,
            "progress": min(progress, goal),
            "currency_reward": int(q.get("currency_reward", 0)),
            "completed": progress >= goal,
            "claimed": is_claimed(account, spec.id, q["code"]),
        })

    milestones = []
    redeemed = set(redeemed_milestones(account, spec.id))
    for idx, m in enumerate(spec.milestones):
        cost = int(m.get("cost", 0))
        milestones.append({
            "idx": idx,
            "title": m.get("title", f"Milestone {idx+1}"),
            "cost": cost,
            "contents": m.get("contents", {}),
            "redeemed": idx in redeemed,
            "affordable": balance >= cost,
        })

    return {
        "id": spec.id,
        "display_name": spec.display_name,
        "starts_at": spec.starts_at.isoformat() + "Z",
        "ends_at": spec.ends_at.isoformat() + "Z",
        "currency_name": spec.currency_name,
        "currency_emoji": spec.currency_emoji,
        "currency_balance": balance,
        "drops": spec.drops,
        "quests": quests,
        "milestones": milestones,
        "live": has_live_row,
    }


@router.post("/quests/{code}/claim", status_code=status.HTTP_201_CREATED)
def claim_event_quest(
    code: str,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    spec = _require_active_event()
    quest = spec.quest_by_code(code)
    if quest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"quest {code!r} not in event {spec.id!r}")

    progress = quest_progress(account, spec.id, code)
    goal = int(quest.get("goal", 1))
    if progress < goal:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"quest not complete ({progress} / {goal})",
        )
    if is_claimed(account, spec.id, code):
        raise HTTPException(status.HTTP_409_CONFLICT, "already claimed")

    reward = int(quest.get("currency_reward", 0))
    if not claim_quest(account, spec.id, code):
        # Race-condition fallback (shouldn't happen with single-threaded request).
        raise HTTPException(status.HTTP_409_CONFLICT, "already claimed")

    new_balance = grant_currency(account, spec.id, reward) if reward > 0 else currency_balance(account, spec.id)
    db.commit()
    return {
        "claimed_quest": code,
        "currency_granted": reward,
        "currency_balance": new_balance,
    }


@router.post("/milestones/{idx}/redeem", status_code=status.HTTP_201_CREATED)
def redeem_event_milestone(
    idx: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    spec = _require_active_event()
    if idx < 0 or idx >= len(spec.milestones):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"milestone idx {idx} out of range")

    if idx in redeemed_milestones(account, spec.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "milestone already redeemed")

    milestone = spec.milestones[idx]
    cost = int(milestone.get("cost", 0))
    if not spend_currency(account, spec.id, cost):
        balance = currency_balance(account, spec.id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough {spec.currency_name or 'currency'} (need {cost}, have {balance})",
        )

    granted = _grant_milestone(db, account, milestone.get("contents", {}))
    redeem_milestone(account, spec.id, idx)
    db.commit()
    return {
        "redeemed_idx": idx,
        "spent": cost,
        "currency_balance": currency_balance(account, spec.id),
        "granted": granted,
    }
