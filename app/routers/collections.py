"""Collections endpoints.

GET  /collections                     — all 12 collections + per-account progress
POST /collections/{code}/claim         — claim completed reward
POST /collections/8-track/open         — consume 1 8-track, return 1-3 pieces
"""
from __future__ import annotations

import json
import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collections import claim_reward, open_eight_track, read_progress
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, Collection

router = APIRouter(prefix="/collections", tags=["collections"])


def _summarize_reward(reward: dict) -> str:
    kind = reward.get("kind")
    if kind == "frame":
        return f"Cosmetic frame: {reward.get('frame_code', '?')}"
    if kind == "currency":
        bits = []
        if reward.get("coins"): bits.append(f"{reward['coins']} coins")
        if reward.get("gems"): bits.append(f"{reward['gems']} gems")
        if reward.get("shards"): bits.append(f"{reward['shards']} shards")
        if reward.get("frame_code"): bits.append(f"frame: {reward['frame_code']}")
        return ", ".join(bits) or "currency"
    if kind == "hero_shards":
        return f"{reward.get('amount', 0)} hero shards ({reward.get('rarity', 'EPIC')})"
    return "?"


@router.get("")
def list_collections(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    rows = list(db.scalars(select(Collection).order_by(Collection.sort_order)).all())
    out = []
    for c in rows:
        pieces_def = json.loads(c.pieces_json)
        progress = read_progress(account, c.code)
        owned = set(progress["pieces"])
        out.append({
            "code": c.code,
            "name": c.name,
            "theme": c.theme,
            "rarity": c.rarity,
            "level_bracket": c.level_bracket,
            "pieces": [
                {
                    "code": p["code"],
                    "name": p["name"],
                    "icon": p["icon"],
                    "owned": p["code"] in owned,
                    "is_completion_piece": p["is_completion_piece"],
                }
                for p in pieces_def
            ],
            "owned_count": len(owned),
            "total_count": len(pieces_def),
            "completed_at": progress["completed_at"],
            "claimed_at":   progress["claimed_at"],
            "claimable":    progress["completed_at"] is not None and progress["claimed_at"] is None,
            "reward_summary": _summarize_reward(json.loads(c.reward_json)),
        })
    return out


@router.post("/8-track/open")
def open_8track_endpoint(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    rng = random.SystemRandom()
    drops = open_eight_track(db, account, rng=rng)
    db.commit()
    return {
        "pieces": [
            {
                "collection_code": d.collection_code,
                "piece_code":      d.piece_code,
                "name":            d.name,
                "icon":            d.icon,
                "is_completion_piece": d.is_completion_piece,
            }
            for d in drops
        ]
    }


@router.post("/{code}/claim")
def claim_collection(
    code: str,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    if db.get(Collection, code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "collection not found")
    granted = claim_reward(db, account, code)
    db.commit()
    return {"granted": granted}
