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


def test_battle_after_three_losses_clears_or_resets_pity(client, db_session):
    """When pity is at 3 and the player runs a battle, the discount fires
    (consumed=True is set during start). After the battle resolves the pity
    state advances per spec: WIN clears both keys, LOSS-after-consumed resets."""
    from sqlalchemy import select

    from app.models import Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty
    from app.security import issue_token
    from app.fail_pity import read_pity

    acc = Account(email="pity_e2e@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    # Use a NORMAL stage to avoid power-floor / unlock chain.
    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    assert normal is not None

    # Give the account 3 minimal-power heroes.
    common_tmpl = db_session.scalar(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.COMMON).limit(1)
    )
    assert common_tmpl is not None
    hero_ids: list[int] = []
    for _ in range(3):
        hi = HeroInstance(account_id=acc.id, template_id=common_tmpl.id, level=1, xp=0)
        db_session.add(hi)
        db_session.flush()
        hero_ids.append(hi.id)
    db_session.commit()

    # Set pity count to 3 (just below the to-fire threshold check, exactly at it).
    acc.stage_pity_json = json.dumps({f"{normal.code}:NORMAL": 3})
    db_session.commit()

    db_session.refresh(acc)
    count, consumed = read_pity(acc, normal.code, StageDifficulty.NORMAL)
    assert count == 3
    assert consumed is False

    # Run battle.
    token = issue_token(acc.id, acc.token_version)
    r = client.post(
        "/battles",
        headers={"Authorization": f"Bearer {token}"},
        json={"stage_id": normal.id, "team": hero_ids},
    )
    assert r.status_code == 201, r.text

    # After battle, pity state must have advanced. Per spec:
    # - WIN: both keys cleared (count=0, consumed=False)
    # - LOSS (consumed was set during start): cycle resets — count=0, consumed=False
    # Either way the post-state is (0, False).
    db_session.refresh(acc)
    count_after, consumed_after = read_pity(acc, normal.code, StageDifficulty.NORMAL)
    assert count_after == 0, f"expected count=0, got {count_after}; outcome={r.json().get('outcome')}"
    assert consumed_after is False
