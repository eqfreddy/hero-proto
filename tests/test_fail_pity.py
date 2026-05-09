"""Fail-pity tests."""
import json

from app.models import Account
from app.fail_pity import (
    read_pity,
    apply_battle_start,
    apply_battle_end,
    PITY_LOSS_THRESHOLD,
    PITY_HP_MULT,
)
from app.models import StageDifficulty


def _make_account(db_session) -> "Account":
    from app.models import Account
    n = db_session.info.get("counter", 0)
    db_session.info["counter"] = n + 1
    acc = Account(email=f"pity_{n}@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    return acc


def test_account_has_stage_pity_json_column(db_session):
    """New accounts get an empty stage_pity_json blob by default."""
    acc = Account(email="pity_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.stage_pity_json == "{}"
    parsed = json.loads(acc.stage_pity_json)
    assert parsed == {}


def test_read_pity_default_zero(db_session):
    acc = _make_account(db_session)
    count, consumed = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert count == 0
    assert consumed is False


def test_apply_battle_start_no_discount_under_threshold(db_session):
    acc = _make_account(db_session)
    mult = apply_battle_start(acc, "1-1", StageDifficulty.HARD)
    assert mult == 1.0
    count, consumed = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert count == 0 and consumed is False


def test_apply_battle_start_discount_at_threshold(db_session):
    acc = _make_account(db_session)
    import json
    acc.stage_pity_json = json.dumps({"1-1:HARD": 3})

    mult = apply_battle_start(acc, "1-1", StageDifficulty.HARD)
    assert mult == PITY_HP_MULT  # 0.9
    count, consumed = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert count == 3
    assert consumed is True


def test_apply_battle_end_win_clears_pity(db_session):
    acc = _make_account(db_session)
    import json
    acc.stage_pity_json = json.dumps({
        "1-1:HARD": 3,
        "1-1:HARD:_consumed": True,
    })

    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=True)
    count, consumed = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert count == 0
    assert consumed is False


def test_apply_battle_end_loss_increments(db_session):
    acc = _make_account(db_session)
    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=False)
    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=False)
    count, consumed = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert count == 2
    assert consumed is False


def test_apply_battle_end_loss_after_consumed_resets(db_session):
    acc = _make_account(db_session)
    import json
    acc.stage_pity_json = json.dumps({
        "1-1:HARD": 3,
        "1-1:HARD:_consumed": True,
    })

    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=False)
    count, consumed = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert count == 0
    assert consumed is False


def test_pity_keys_isolated_per_stage_and_tier(db_session):
    acc = _make_account(db_session)
    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=False)
    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=False)
    apply_battle_end(acc, "1-1", StageDifficulty.HARD, won=False)
    n_count, _ = read_pity(acc, "1-1", StageDifficulty.NIGHTMARE)
    assert n_count == 0
    other_count, _ = read_pity(acc, "1-2", StageDifficulty.HARD)
    assert other_count == 0
    h_count, _ = read_pity(acc, "1-1", StageDifficulty.HARD)
    assert h_count == 3
