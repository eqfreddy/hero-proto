"""Fail-pity tests."""
import json

from app.models import Account


def test_account_has_stage_pity_json_column(db_session):
    """New accounts get an empty stage_pity_json blob by default."""
    acc = Account(email="pity_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.stage_pity_json == "{}"
    parsed = json.loads(acc.stage_pity_json)
    assert parsed == {}
