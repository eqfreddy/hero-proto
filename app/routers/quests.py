"""Quest endpoints.

GET  /quests/active              — active (unclaimed, undismissed) quests + progress
POST /quests/{quest_id}/claim    — body: {"choice": "epic"|"gems"}, grants reward
POST /quests/{quest_id}/dismiss  — hides widget; reversible from account settings
"""
from __future__ import annotations

import json
import logging
import random
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.models import Account, AccountQuest, GachaRecord, HeroInstance, HeroTemplate, Quest, Rarity, utcnow

router = APIRouter(prefix="/quests", tags=["quests"])
log = logging.getLogger(__name__)


def _build_task_out(task: dict, progress: dict) -> dict:
    from app.quest_service import DAY_TRACKING_TASK_ID, DAY_TRACKING_PROGRESS_KEY
    task_id = task["id"]
    target = int(task["target"])
    if task_id == DAY_TRACKING_TASK_ID:
        current = len(progress.get(DAY_TRACKING_PROGRESS_KEY, []))
    else:
        current = int(progress.get(task_id, 0))
    return {
        "id": task_id,
        "label": task["label"],
        "event": task["event"],
        "target": target,
        "current": min(current, target),
        "done": current >= target,
    }


def _quest_out(aq: AccountQuest, quest: Quest) -> dict:
    tasks_def = json.loads(quest.tasks_json)
    progress = json.loads(aq.progress_json)
    reward = json.loads(quest.reward_json)
    tasks_out = [_build_task_out(t, progress) for t in tasks_def]
    done_count = sum(1 for t in tasks_out if t["done"])
    return {
        "id": aq.id,
        "quest_id": aq.quest_id,
        "name": quest.name,
        "description": quest.description,
        "tasks": tasks_out,
        "done_count": done_count,
        "total_count": len(tasks_out),
        "completed_at": aq.completed_at.isoformat() if aq.completed_at else None,
        "claimed_at": aq.claimed_at.isoformat() if aq.claimed_at else None,
        "claim_choice": aq.claim_choice,
        "dismissed": aq.dismissed,
        "reward": reward,
    }


@router.get("/active")
def active_quests(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    rows = (
        db.query(AccountQuest)
        .filter(
            AccountQuest.account_id == account.id,
            AccountQuest.claimed_at.is_(None),
            AccountQuest.dismissed.is_(False),
        )
        .all()
    )
    out = []
    for aq in rows:
        quest = db.get(Quest, aq.quest_id)
        if quest is None:
            continue
        out.append(_quest_out(aq, quest))
    return out


class ClaimIn(BaseModel):
    choice: Literal["epic", "gems"]


@router.post("/{quest_id}/claim")
def claim_quest(
    quest_id: str,
    body: ClaimIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    aq = (
        db.execute(
            select(AccountQuest)
            .filter_by(account_id=account.id, quest_id=quest_id)
            .with_for_update()
        ).scalar_one_or_none()
    )
    if aq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "quest not found")
    if aq.completed_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quest not complete")
    if aq.claimed_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "already claimed")

    quest = db.get(Quest, quest_id)
    reward = json.loads(quest.reward_json) if quest else {}

    # Always-granted cosmetic frame.
    frame_code = reward.get("cosmetic_frame", "survived_onboarding")
    try:
        frames: list[str] = json.loads(account.cosmetic_frames_json or "[]")
    except Exception:
        frames = []
    if frame_code not in frames:
        frames.append(frame_code)
        account.cosmetic_frames_json = json.dumps(frames)

    # Choice reward.
    granted: dict = {"cosmetic_frame": frame_code}
    if body.choice == "gems":
        account.gems = (account.gems or 0) + 500
        granted["gems"] = 500
    elif body.choice == "epic":
        rng = random.SystemRandom()
        pool = list(db.query(HeroTemplate).filter(HeroTemplate.rarity == Rarity.EPIC).all())
        if not pool:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "no epic heroes available; try again later")
        template = rng.choice(pool)
        hero = HeroInstance(
            account_id=account.id,
            template_id=template.id,
            level=1,
            xp=0,
        )
        db.add(hero)
        db.flush()
        db.add(GachaRecord(
            account_id=account.id,
            template_id=template.id,
            rarity=str(Rarity.EPIC),
            pity_before=account.pulls_since_epic or 0,
        ))
        account.pulls_since_epic = 0  # reset pity counter after Epic grant
        granted["epic_hero"] = {"template_id": template.id, "name": template.name}

    aq.claimed_at = utcnow()
    aq.claim_choice = body.choice
    db.commit()

    return {"granted": granted}


@router.post("/{quest_id}/dismiss")
def dismiss_quest(
    quest_id: str,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    aq = (
        db.query(AccountQuest)
        .filter_by(account_id=account.id, quest_id=quest_id)
        .first()
    )
    if aq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "quest not found")
    aq.dismissed = True
    db.commit()
    return {"dismissed": True}
