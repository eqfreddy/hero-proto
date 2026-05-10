"""Rare-collection v1 tests."""
import json

from app.models import Account, Collection


def test_account_has_collection_columns(db_session):
    """New accounts get an empty collection_progress_json blob and 0 eight_tracks."""
    acc = Account(email="coll_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.collection_progress_json == "{}"
    assert json.loads(acc.collection_progress_json) == {}
    assert acc.eight_tracks == 0


def test_collection_model_exists(db_session):
    """Collection table can store a row with required fields."""
    c = Collection(
        code="test_floppy",
        name="Test Floppy",
        theme="testing",
        rarity="UNCOMMON",
        level_bracket="1-20",
        pieces_json=json.dumps([{"code": "p1", "name": "P1", "icon": "💾", "flavor": "x", "is_completion_piece": False}]),
        reward_json=json.dumps({"kind": "frame", "frame_code": "test"}),
        sort_order=0,
    )
    db_session.add(c)
    db_session.flush()
    db_session.refresh(c)
    assert c.code == "test_floppy"
    assert c.rarity == "UNCOMMON"


import pytest
import json


@pytest.fixture(autouse=True)
def _seed_collections_fixture(db_session):
    """Seed collections before each collection test."""
    from app.seed import seed_collections
    seed_collections(db_session)


def test_seed_produces_12_collections(db_session):
    """Seed loop creates the 12 v1 collections, 4 rarities × 3 brackets."""
    from sqlalchemy import select
    rows = db_session.scalars(select(Collection)).all()
    rarities = {r.rarity for r in rows}
    brackets = {r.level_bracket for r in rows}
    assert len(rows) == 12, f"expected 12 collections, got {len(rows)}"
    assert rarities == {"UNCOMMON", "RARE", "EPIC", "LEGENDARY"}
    assert brackets == {"1-20", "21-40", "41-60"}
    # Each collection has at least 5 pieces, at most 12.
    for c in rows:
        pieces = json.loads(c.pieces_json)
        assert 5 <= len(pieces) <= 12, f"{c.code}: {len(pieces)} pieces out of range"
        completion_pieces = [p for p in pieces if p["is_completion_piece"]]
        assert len(completion_pieces) == 1, f"{c.code}: must have exactly 1 completion piece"


import random
from datetime import datetime

from app.collections import (
    DROP_CHANCE_REGULAR, DROP_CHANCE_BOSS, DROP_CHANCE_RAID,
    EIGHT_TRACK_PIECE_WEIGHTS, RARITY_WEIGHTS, DUP_COIN_AWARD,
    bracket_for_level,
    is_boss_stage,
    read_progress,
    award_piece,
    try_complete,
    roll_piece_drop,
    open_eight_track,
    claim_reward,
)


def _make_account(db_session, level=10, eight_tracks=0):
    n = db_session.info.get("counter", 0)
    db_session.info["counter"] = n + 1
    acc = Account(
        email=f"coll_eng_{n}@example.com", password_hash="x",
        account_level=level,
        eight_tracks=eight_tracks,
    )
    db_session.add(acc); db_session.flush()
    return acc


def test_constants():
    assert DROP_CHANCE_REGULAR == 0.07
    assert DROP_CHANCE_BOSS == 0.20
    assert DROP_CHANCE_RAID == 0.05
    assert RARITY_WEIGHTS == {"UNCOMMON": 0.50, "RARE": 0.30, "EPIC": 0.15, "LEGENDARY": 0.05}
    assert DUP_COIN_AWARD == 5
    s = sum(EIGHT_TRACK_PIECE_WEIGHTS.values())
    assert abs(s - 1.0) < 0.001


def test_bracket_for_level():
    assert bracket_for_level(1) == "1-20"
    assert bracket_for_level(20) == "1-20"
    assert bracket_for_level(21) == "21-40"
    assert bracket_for_level(40) == "21-40"
    assert bracket_for_level(41) == "41-60"
    assert bracket_for_level(60) == "41-60"
    assert bracket_for_level(75) == "any"


def test_is_boss_stage():
    """Last stage of any chapter in STORY_CHAPTERS is a boss."""
    from app.account_level import STORY_CHAPTERS
    saw_boss = False
    saw_non_boss = False
    for chapter in STORY_CHAPTERS:
        if chapter.stages:
            last = chapter.stages[-1].code
            assert is_boss_stage(last) is True
            saw_boss = True
            if len(chapter.stages) > 1:
                first = chapter.stages[0].code
                if first != last:
                    assert is_boss_stage(first) is False
                    saw_non_boss = True
    assert saw_boss
    # Unknown stage codes are not bosses.
    assert is_boss_stage("nonexistent_stage") is False


def test_read_progress_default_empty(db_session):
    acc = _make_account(db_session)
    p = read_progress(acc, "cubicle_detritus")
    assert p["pieces"] == []
    assert p["completed_at"] is None
    assert p["claimed_at"] is None


def test_award_piece_new(db_session):
    acc = _make_account(db_session)
    status = award_piece(acc, "cubicle_detritus", "paperclip_red")
    assert status == "new"
    p = read_progress(acc, "cubicle_detritus")
    assert "paperclip_red" in p["pieces"]


def test_award_piece_duplicate(db_session):
    acc = _make_account(db_session)
    award_piece(acc, "cubicle_detritus", "paperclip_red")
    status = award_piece(acc, "cubicle_detritus", "paperclip_red")
    assert status == "duplicate"
    p = read_progress(acc, "cubicle_detritus")
    assert p["pieces"].count("paperclip_red") == 1


def test_try_complete(db_session):
    acc = _make_account(db_session)
    c = db_session.get(Collection, "cubicle_detritus")
    pieces = [p["code"] for p in json.loads(c.pieces_json)]
    for code in pieces[:-1]:
        award_piece(acc, "cubicle_detritus", code)
    assert try_complete(acc, "cubicle_detritus") is False
    award_piece(acc, "cubicle_detritus", pieces[-1])
    assert try_complete(acc, "cubicle_detritus") is True
    p = read_progress(acc, "cubicle_detritus")
    assert p["completed_at"] is not None
    # Idempotent: second try_complete returns False
    assert try_complete(acc, "cubicle_detritus") is False


def test_roll_piece_drop_picks_from_player_bracket(db_session):
    acc = _make_account(db_session, level=10)  # bracket 1-20
    rng = random.Random(7)
    drop = roll_piece_drop(db_session, acc, source="stage", rng=rng)
    assert drop is not None
    assert drop.collection_code in {
        "cubicle_detritus", "onboarding_kit", "helpdesk_starter", "y2k_relics",
    }


def test_roll_piece_drop_skips_completed_collections(db_session):
    acc = _make_account(db_session, level=10)
    c = db_session.get(Collection, "cubicle_detritus")
    pieces = [p["code"] for p in json.loads(c.pieces_json)]
    for code in pieces:
        award_piece(acc, "cubicle_detritus", code)
    try_complete(acc, "cubicle_detritus")
    rng = random.Random(0)
    seen = set()
    for _ in range(50):
        drop = roll_piece_drop(db_session, acc, source="stage", rng=rng)
        if drop:
            seen.add(drop.collection_code)
    assert "cubicle_detritus" not in seen


def test_claim_reward_currency(db_session):
    from app.models import Collection
    acc = _make_account(db_session, level=10)
    initial_coins = acc.coins or 0
    initial_gems = acc.gems or 0
    c = db_session.get(Collection, "onboarding_kit")
    for p in json.loads(c.pieces_json):
        award_piece(acc, "onboarding_kit", p["code"])
    try_complete(acc, "onboarding_kit")
    granted = claim_reward(db_session, acc, "onboarding_kit")
    assert granted["kind"] == "currency"
    assert acc.coins == initial_coins + 500
    assert acc.gems == initial_gems + 50
    # Second claim raises
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        claim_reward(db_session, acc, "onboarding_kit")


def test_claim_reward_frame(db_session):
    from app.models import Collection
    acc = _make_account(db_session, level=10)
    c = db_session.get(Collection, "cubicle_detritus")
    for p in json.loads(c.pieces_json):
        award_piece(acc, "cubicle_detritus", p["code"])
    try_complete(acc, "cubicle_detritus")
    granted = claim_reward(db_session, acc, "cubicle_detritus")
    assert granted["kind"] == "frame"
    frames = json.loads(acc.cosmetic_frames_json or "[]")
    assert "cubicle_archaeologist" in frames


def test_open_eight_track_consumes_inventory(db_session):
    acc = _make_account(db_session, level=10, eight_tracks=2)
    rng = random.Random(0)
    pieces = open_eight_track(db_session, acc, rng=rng)
    assert acc.eight_tracks == 1
    assert isinstance(pieces, list)
    # Second open
    open_eight_track(db_session, acc, rng=rng)
    assert acc.eight_tracks == 0
    # Third raises
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        open_eight_track(db_session, acc, rng=rng)
