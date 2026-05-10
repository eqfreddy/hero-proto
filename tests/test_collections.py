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


def test_battle_win_can_drop_collection_piece(client, db_session):
    """A battle WIN occasionally fires a collection_drop in rewards_extra.
    7% rate × 60 trials ≈ 98% probability of seeing at least one drop."""
    from sqlalchemy import select
    from app.models import Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty
    from app.security import issue_token

    acc = Account(email="coll_battle@example.com", password_hash="x", account_level=5)
    db_session.add(acc); db_session.flush()

    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    epic_tmpl = db_session.scalar(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.EPIC).limit(1)
    ) or db_session.scalar(select(HeroTemplate).limit(1))

    hero_ids: list[int] = []
    for _ in range(3):
        hi = HeroInstance(account_id=acc.id, template_id=epic_tmpl.id, level=50, xp=0, stars=5)
        db_session.add(hi); db_session.flush()
        hero_ids.append(hi.id)
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    saw_drop = False
    for _ in range(60):
        r = client.post(
            "/battles",
            headers={"Authorization": f"Bearer {token}"},
            json={"stage_id": normal.id, "team": hero_ids},
        )
        if r.status_code != 201:
            continue
        body = r.json()
        # rewards_extra is in body.rewards_json or body.rewards depending on schema
        rewards = body.get("rewards") or body.get("rewards_json") or {}
        if isinstance(rewards, str):
            import json as _json
            try:
                rewards = _json.loads(rewards)
            except Exception:
                rewards = {}
        if rewards.get("collection_drop"):
            saw_drop = True
            break
    assert saw_drop, "no collection drop after 60 battles — wiring may be broken"


def test_collections_api_returns_progress(client, db_session):
    from app.models import Account
    from app.security import issue_token

    acc = Account(email="coll_api@example.com", password_hash="x", account_level=10)
    db_session.add(acc); db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/collections", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 12
    sample = next(r for r in rows if r["code"] == "cubicle_detritus")
    assert sample["name"] == "Cubicle Detritus"
    assert sample["rarity"] == "UNCOMMON"
    assert sample["level_bracket"] == "1-20"
    assert sample["owned_count"] == 0
    assert sample["total_count"] >= 5
    assert sample["claimable"] is False
    for p in sample["pieces"]:
        assert "code" in p and "name" in p and "icon" in p
        assert "owned" in p


def test_collections_claim_grants_reward(client, db_session):
    from app.models import Account, Collection
    from app.security import issue_token
    from app.collections import award_piece, try_complete

    acc = Account(email="coll_claim@example.com", password_hash="x", account_level=10, coins=0, gems=0)
    db_session.add(acc); db_session.flush()
    c = db_session.get(Collection, "onboarding_kit")
    for p in json.loads(c.pieces_json):
        award_piece(acc, "onboarding_kit", p["code"])
    try_complete(acc, "onboarding_kit")
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.post("/collections/onboarding_kit/claim", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["granted"]["kind"] == "currency"
    assert body["granted"]["coins"] == 500

    r2 = client.post("/collections/onboarding_kit/claim", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 400


def test_collections_8track_requires_inventory(client, db_session):
    from app.models import Account
    from app.security import issue_token

    acc = Account(email="coll_8t_empty@example.com", password_hash="x", account_level=10, eight_tracks=0)
    db_session.add(acc); db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.post("/collections/8-track/open", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400


def test_collections_8track_consumes_and_returns_pieces(client, db_session):
    from app.models import Account
    from app.security import issue_token

    acc = Account(email="coll_8t_full@example.com", password_hash="x", account_level=10, eight_tracks=1)
    db_session.add(acc); db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.post("/collections/8-track/open", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "pieces" in body
    db_session.refresh(acc)
    assert acc.eight_tracks == 0


def test_grant_eight_track_idempotent(db_session):
    """Same source key only grants once."""
    from app.collections import grant_eight_track
    acc = _make_account(db_session, level=10, eight_tracks=0)
    assert grant_eight_track(acc, source="tower_floor_50") is True
    assert acc.eight_tracks == 1
    assert grant_eight_track(acc, source="tower_floor_50") is False
    assert acc.eight_tracks == 1
    # Different source grants separately
    assert grant_eight_track(acc, source="weekly_2026_w19") is True
    assert acc.eight_tracks == 2


def test_tower_floor_50_grants_eight_track_once(db_session):
    """Crossing floor 50 for the first time grants 1 8-track; second crossing doesn't."""
    from app.collections import grant_eight_track
    acc = _make_account(db_session, level=70, eight_tracks=0)
    # Simulate tower floor crossing
    grant_eight_track(acc, source="tower_floor_50")
    assert acc.eight_tracks == 1
    grant_eight_track(acc, source="tower_floor_50")  # idempotent
    assert acc.eight_tracks == 1


def test_weekly_chest_grants_per_iso_week(db_session):
    """Different ISO weeks grant separately; same week is idempotent."""
    from app.collections import grant_eight_track
    acc = _make_account(db_session, level=10, eight_tracks=0)
    grant_eight_track(acc, source="weekly_2026_w19")
    assert acc.eight_tracks == 1
    grant_eight_track(acc, source="weekly_2026_w19")  # same week, idempotent
    assert acc.eight_tracks == 1
    grant_eight_track(acc, source="weekly_2026_w20")  # next week
    assert acc.eight_tracks == 2


def test_me_includes_eight_tracks(client, db_session):
    from app.models import Account
    from app.security import issue_token
    acc = Account(email="me_8t@example.com", password_hash="x", eight_tracks=3)
    db_session.add(acc); db_session.commit()
    token = issue_token(acc.id, acc.token_version)
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["eight_tracks"] == 3
