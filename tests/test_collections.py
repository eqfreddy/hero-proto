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
