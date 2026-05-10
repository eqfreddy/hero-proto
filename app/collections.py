"""Rare-collection v1 engine.

State lives on Account.collection_progress_json:
  {"<collection_code>": {"pieces": [...], "completed_at": "...", "claimed_at": "..."}}

8-track inventory lives on Account.eight_tracks (Integer).

Helpers do not commit — the caller (battle resolver, API endpoint) owns the
transaction. Defensive _load returns {} on corrupt JSON.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.models import Account, Collection, HeroInstance, HeroTemplate, utcnow

log = logging.getLogger(__name__)

DROP_CHANCE_REGULAR = 0.07
DROP_CHANCE_BOSS = 0.20
DROP_CHANCE_RAID = 0.05

RARITY_WEIGHTS: dict[str, float] = {
    "UNCOMMON":  0.50,
    "RARE":      0.30,
    "EPIC":      0.15,
    "LEGENDARY": 0.05,
}

EIGHT_TRACK_PIECE_WEIGHTS: dict[int, float] = {1: 0.6, 2: 0.3, 3: 0.1}
DUP_COIN_AWARD = 5


@dataclass
class CollectionDrop:
    collection_code: str
    piece_code: str
    name: str
    icon: str
    is_completion_piece: bool


def bracket_for_level(level: int) -> str:
    if level <= 20:
        return "1-20"
    if level <= 40:
        return "21-40"
    if level <= 60:
        return "41-60"
    return "any"


def is_boss_stage(stage_code: str) -> bool:
    """True if this stage is the final stage of any narrative chapter."""
    from app.account_level import STORY_CHAPTERS
    for chapter in STORY_CHAPTERS:
        if chapter.stages and chapter.stages[-1].code == stage_code:
            return True
    return False


def _load_all(account: Account) -> dict:
    try:
        return json.loads(account.collection_progress_json or "{}")
    except (json.JSONDecodeError, TypeError):
        log.warning("collection_progress_json corrupt for account=%s; resetting", account.id)
        return {}


def _save_all(account: Account, data: dict) -> None:
    account.collection_progress_json = json.dumps(data)


def read_progress(account: Account, collection_code: str) -> dict:
    data = _load_all(account)
    entry = data.get(collection_code) or {}
    return {
        "pieces":       list(entry.get("pieces", [])),
        "completed_at": entry.get("completed_at"),
        "claimed_at":   entry.get("claimed_at"),
    }


def _set_progress(account: Account, collection_code: str, progress: dict) -> None:
    data = _load_all(account)
    data[collection_code] = progress
    _save_all(account, data)


def award_piece(account: Account, collection_code: str, piece_code: str) -> Literal["new", "duplicate"]:
    progress = read_progress(account, collection_code)
    if piece_code in progress["pieces"]:
        return "duplicate"
    progress["pieces"].append(piece_code)
    _set_progress(account, collection_code, progress)
    return "new"


def try_complete(account: Account, collection_code: str) -> bool:
    progress = read_progress(account, collection_code)
    if progress["completed_at"] is not None:
        return False
    sess = object_session(account)
    if sess is None:
        return False
    c = sess.get(Collection, collection_code)
    if c is None:
        return False
    total = len(json.loads(c.pieces_json))
    if len(progress["pieces"]) >= total:
        progress["completed_at"] = utcnow().isoformat()
        _set_progress(account, collection_code, progress)
        return True
    return False


def roll_piece_drop(
    db: Session,
    account: Account,
    *,
    source: Literal["stage", "boss", "raid", "8-track"],
    rng: random.Random,
    raid_pool_only: bool = False,
) -> CollectionDrop | None:
    bracket = bracket_for_level(int(account.account_level or 1))

    q = select(Collection)
    if bracket != "any":
        q = q.where(Collection.level_bracket == bracket)
    candidates = list(db.scalars(q).all())
    if not candidates:
        return None

    progress_all = _load_all(account)
    candidates = [
        c for c in candidates
        if (progress_all.get(c.code) or {}).get("completed_at") is None
    ]
    if not candidates:
        return None

    weights = [RARITY_WEIGHTS.get(c.rarity, 0.01) for c in candidates]
    chosen = rng.choices(candidates, weights=weights, k=1)[0]

    pieces = json.loads(chosen.pieces_json)
    owned = set((progress_all.get(chosen.code) or {}).get("pieces", []))
    unowned = [p for p in pieces if p["code"] not in owned]
    if not unowned:
        return None

    # Prefer non-completion pieces when there are other options
    if source == "stage" and len(unowned) > 1:
        non_completion = [p for p in unowned if not p["is_completion_piece"]]
        if non_completion:
            unowned = non_completion

    chosen_piece = rng.choice(unowned)
    return CollectionDrop(
        collection_code=chosen.code,
        piece_code=chosen_piece["code"],
        name=chosen_piece["name"],
        icon=chosen_piece["icon"],
        is_completion_piece=chosen_piece["is_completion_piece"],
    )


def open_eight_track(
    db: Session,
    account: Account,
    *,
    rng: random.Random,
) -> list[CollectionDrop]:
    if (account.eight_tracks or 0) <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no 8-tracks")
    account.eight_tracks -= 1

    counts = list(EIGHT_TRACK_PIECE_WEIGHTS.keys())
    weights = list(EIGHT_TRACK_PIECE_WEIGHTS.values())
    n = rng.choices(counts, weights=weights, k=1)[0]

    drops: list[CollectionDrop] = []
    for _ in range(n):
        drop = roll_piece_drop(db, account, source="8-track", rng=rng)
        if drop is None:
            continue
        status_str = award_piece(account, drop.collection_code, drop.piece_code)
        if status_str == "duplicate":
            account.coins = (account.coins or 0) + DUP_COIN_AWARD
        else:
            try_complete(account, drop.collection_code)
            drops.append(drop)
    return drops


def claim_reward(db: Session, account: Account, collection_code: str) -> dict:
    progress = read_progress(account, collection_code)
    if progress["completed_at"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "collection not complete")
    if progress["claimed_at"] is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "already claimed")

    c = db.get(Collection, collection_code)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "collection not found")
    reward = json.loads(c.reward_json)

    granted: dict = {"kind": reward.get("kind")}

    if reward.get("kind") == "frame":
        frame_code = reward["frame_code"]
        try:
            frames = json.loads(account.cosmetic_frames_json or "[]")
        except Exception:
            frames = []
        if frame_code not in frames:
            frames.append(frame_code)
            account.cosmetic_frames_json = json.dumps(frames)
        granted["frame_code"] = frame_code

    elif reward.get("kind") == "currency":
        if "coins" in reward:
            account.coins = (account.coins or 0) + int(reward["coins"])
            granted["coins"] = int(reward["coins"])
        if "gems" in reward:
            account.gems = (account.gems or 0) + int(reward["gems"])
            granted["gems"] = int(reward["gems"])
        if "shards" in reward:
            account.shards = (account.shards or 0) + int(reward["shards"])
            granted["shards"] = int(reward["shards"])
        if "frame_code" in reward:
            try:
                frames = json.loads(account.cosmetic_frames_json or "[]")
            except Exception:
                frames = []
            if reward["frame_code"] not in frames:
                frames.append(reward["frame_code"])
                account.cosmetic_frames_json = json.dumps(frames)
            granted["frame_code"] = reward["frame_code"]

    elif reward.get("kind") == "hero_shards":
        amount = int(reward.get("amount", 0))
        target_rarity = reward.get("rarity", "EPIC")
        owned_templates = list(db.scalars(
            select(HeroTemplate)
            .join(HeroInstance, HeroInstance.template_id == HeroTemplate.id)
            .where(HeroInstance.account_id == account.id)
            .distinct()
        ).all())
        target = next((t for t in owned_templates if str(t.rarity) == target_rarity), None)
        if target is None:
            rarity_order = {"COMMON": 0, "RARE": 1, "EPIC": 2, "LEGENDARY": 3, "MYTH": 4}
            owned_templates_sorted = sorted(
                owned_templates,
                key=lambda t: rarity_order.get(str(t.rarity), -1),
                reverse=True,
            )
            target = owned_templates_sorted[0] if owned_templates_sorted else None
        if target is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "no heroes to grant shards for; try again after summoning",
            )
        try:
            shards_map = json.loads(account.template_shards_json or "{}")
        except Exception:
            shards_map = {}
        shards_map[target.code] = int(shards_map.get(target.code, 0)) + amount
        account.template_shards_json = json.dumps(shards_map)
        granted["template_code"] = target.code
        granted["amount"] = amount

    progress["claimed_at"] = utcnow().isoformat()
    _set_progress(account, collection_code, progress)
    return granted


def grant_eight_track(account: Account, *, source: str) -> bool:
    """Grant 1 8-track if `source` hasn't already paid out for this player.

    Returns True if granted, False if already granted (idempotent).

    Tracking: account.collection_progress_json["_eight_track_grants"] = [source, ...].
    For repeating sources (weekly chest), the source string MUST include the period
    — e.g., "weekly_2026_w19" — so different periods grant separately.
    """
    data = _load_all(account)
    granted = data.setdefault("_eight_track_grants", [])
    if source in granted:
        return False
    granted.append(source)
    data["_eight_track_grants"] = granted
    _save_all(account, data)
    account.eight_tracks = (account.eight_tracks or 0) + 1
    return True
