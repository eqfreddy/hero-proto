"""Drop-meter tests."""
import json

from app.models import Account


def test_account_has_stage_drop_pity_json_column(db_session):
    """New accounts get an empty stage_drop_pity_json blob by default."""
    acc = Account(email="drop_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.stage_drop_pity_json == "{}"
    parsed = json.loads(acc.stage_drop_pity_json)
    assert parsed == {}


import random

from app.drop_meter import (
    read_meter,
    increment_and_check,
    force_rarity,
    DROP_METER_CAP,
    GUARANTEE_POOL,
)
from app.models import GearRarity, StageDifficulty


def _make_account(db_session):
    from app.models import Account
    n = db_session.info.get("counter", 0)
    db_session.info["counter"] = n + 1
    acc = Account(email=f"drop_{n}@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    return acc


def test_constants_match_spec():
    assert DROP_METER_CAP == 20
    assert set(GUARANTEE_POOL.keys()) == {
        StageDifficulty.NORMAL,
        StageDifficulty.HARD,
        StageDifficulty.NIGHTMARE,
        StageDifficulty.LEGENDARY,
    }
    assert GUARANTEE_POOL[StageDifficulty.NORMAL] == {GearRarity.RARE: 1.0}
    leg = GUARANTEE_POOL[StageDifficulty.LEGENDARY]
    assert leg[GearRarity.EPIC] == 0.4
    assert leg[GearRarity.LEGENDARY] == 0.6


def test_read_meter_default_zero(db_session):
    acc = _make_account(db_session)
    assert read_meter(acc, "1-1", StageDifficulty.HARD) == 0


def test_increment_and_check_below_cap_returns_false(db_session):
    """First 19 increments return False; counter advances by 1 each call."""
    acc = _make_account(db_session)
    for i in range(1, DROP_METER_CAP):
        triggered = increment_and_check(acc, "1-1", StageDifficulty.HARD)
        assert triggered is False, f"unexpected trigger at run {i}"
        assert read_meter(acc, "1-1", StageDifficulty.HARD) == i


def test_increment_and_check_at_cap_triggers_and_resets(db_session):
    """Run 20 hits cap, returns True, and resets counter to 0."""
    acc = _make_account(db_session)
    import json
    acc.stage_drop_pity_json = json.dumps({"1-1:HARD": 19})
    triggered = increment_and_check(acc, "1-1", StageDifficulty.HARD)
    assert triggered is True
    assert read_meter(acc, "1-1", StageDifficulty.HARD) == 0


def test_increment_independent_per_stage_and_tier(db_session):
    acc = _make_account(db_session)
    increment_and_check(acc, "1-1", StageDifficulty.HARD)
    increment_and_check(acc, "1-1", StageDifficulty.HARD)
    assert read_meter(acc, "1-2", StageDifficulty.HARD) == 0
    assert read_meter(acc, "1-1", StageDifficulty.NIGHTMARE) == 0
    assert read_meter(acc, "1-1", StageDifficulty.HARD) == 2


def test_force_rarity_normal_always_rare():
    rng = random.Random(0)
    for _ in range(50):
        assert force_rarity(StageDifficulty.NORMAL, rng) == GearRarity.RARE


def test_force_rarity_legendary_only_epic_or_legendary():
    rng = random.Random(0)
    for _ in range(100):
        rolled = force_rarity(StageDifficulty.LEGENDARY, rng)
        assert rolled in {GearRarity.EPIC, GearRarity.LEGENDARY}


def test_force_rarity_distribution_matches_weights():
    """Sampling 1000 LEGENDARY rolls should land within tolerance of (0.4, 0.6)."""
    rng = random.Random(42)
    counts = {GearRarity.EPIC: 0, GearRarity.LEGENDARY: 0}
    n = 1000
    for _ in range(n):
        counts[force_rarity(StageDifficulty.LEGENDARY, rng)] += 1
    epic_pct = counts[GearRarity.EPIC] / n
    legendary_pct = counts[GearRarity.LEGENDARY] / n
    assert 0.35 <= epic_pct <= 0.45, f"EPIC pct out of band: {epic_pct}"
    assert 0.55 <= legendary_pct <= 0.65, f"LEGENDARY pct out of band: {legendary_pct}"


def test_battle_at_cap_triggers_meter_reset(client, db_session):
    """When the meter is at cap-1 (19), the next battle WIN forces the trigger
    and resets the counter. The strict assertion is the reset post-WIN."""
    from sqlalchemy import select

    from app.models import (
        Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty,
    )
    from app.security import issue_token
    from app.drop_meter import read_meter, DROP_METER_CAP

    acc = Account(email="drop_e2e@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    assert normal is not None

    # Strong team — we need to WIN for the meter to fire.
    epic_tmpl = db_session.scalar(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.EPIC).limit(1)
    )
    if epic_tmpl is None:
        epic_tmpl = db_session.scalar(select(HeroTemplate).limit(1))
    assert epic_tmpl is not None

    hero_ids: list[int] = []
    for _ in range(3):
        hi = HeroInstance(account_id=acc.id, template_id=epic_tmpl.id, level=50, xp=0, stars=5)
        db_session.add(hi)
        db_session.flush()
        hero_ids.append(hi.id)
    db_session.commit()

    # Set meter to 19 — next WIN triggers.
    import json
    acc.stage_drop_pity_json = json.dumps({f"{normal.code}:NORMAL": DROP_METER_CAP - 1})
    db_session.commit()

    db_session.refresh(acc)
    assert read_meter(acc, normal.code, StageDifficulty.NORMAL) == DROP_METER_CAP - 1

    token = issue_token(acc.id, acc.token_version)
    r = client.post(
        "/battles",
        headers={"Authorization": f"Bearer {token}"},
        json={"stage_id": normal.id, "team": hero_ids},
    )
    assert r.status_code == 201, r.text

    db_session.refresh(acc)
    if r.json().get("outcome") == "WIN":
        # Strict: counter must have reset to 0.
        assert read_meter(acc, normal.code, StageDifficulty.NORMAL) == 0
    else:
        # LOSS — counter unchanged (LOSS doesn't increment).
        assert read_meter(acc, normal.code, StageDifficulty.NORMAL) == DROP_METER_CAP - 1


def test_stages_api_includes_drop_meter_fields(client, db_session):
    """GET /stages returns drop_meter (per-row count) and drop_meter_cap (constant)
    scoped to the caller."""
    from sqlalchemy import select

    from app.models import Account, Stage, StageDifficulty
    from app.security import issue_token
    from app.drop_meter import increment_and_check, DROP_METER_CAP

    acc = Account(email="drop_api@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    for _ in range(5):
        increment_and_check(acc, normal.code, StageDifficulty.NORMAL)
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/stages", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    rows = r.json()

    target = next(row for row in rows if row["code"] == normal.code)
    assert target["drop_meter"] == 5
    assert target["drop_meter_cap"] == DROP_METER_CAP

    other = next(row for row in rows if row["code"] != normal.code and row["difficulty_tier"] == "NORMAL")
    assert other["drop_meter"] == 0
    assert other["drop_meter_cap"] == DROP_METER_CAP
