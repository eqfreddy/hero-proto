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
