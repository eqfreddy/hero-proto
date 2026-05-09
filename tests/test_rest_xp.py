"""Rest-XP tests."""
from datetime import datetime, timedelta

from app.models import Account


def test_account_has_rest_xp_columns(db_session):
    """New accounts get rest_xp_banked_seconds=0 and rest_xp_last_tick_at set to ~now."""
    before = datetime.utcnow()
    acc = Account(email="rest_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.rest_xp_banked_seconds == 0
    assert acc.rest_xp_last_tick_at is not None
    delta = abs((acc.rest_xp_last_tick_at - before).total_seconds())
    assert delta < 5, f"rest_xp_last_tick_at default too far from now: delta={delta}"
