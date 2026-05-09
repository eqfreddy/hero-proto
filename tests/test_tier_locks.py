"""Tier-lock + power-floor tests."""
from app.models import StageDifficulty
from app.tiers import TIER_POWER_FLOOR, tier_power_floor


def test_power_floor_constants():
    assert TIER_POWER_FLOOR[StageDifficulty.NIGHTMARE] == 50_000
    assert TIER_POWER_FLOOR[StageDifficulty.LEGENDARY] == 100_000
    # NORMAL and HARD have no floor.
    assert StageDifficulty.NORMAL not in TIER_POWER_FLOOR
    assert StageDifficulty.HARD not in TIER_POWER_FLOOR


def test_tier_power_floor_helper():
    assert tier_power_floor(StageDifficulty.NORMAL) is None
    assert tier_power_floor(StageDifficulty.HARD) is None
    assert tier_power_floor(StageDifficulty.NIGHTMARE) == 50_000
    assert tier_power_floor(StageDifficulty.LEGENDARY) == 100_000
    # String inputs accepted (for symmetry with xp_per_win).
    assert tier_power_floor("NIGHTMARE") == 50_000
    assert tier_power_floor("BOGUS") is None
    assert tier_power_floor("") is None


def test_legendary_battle_rejects_underpowered_team(client, db_session):
    """A LEGENDARY battle with team power < 100k returns HTTP 400 with required+current."""
    import random as _random
    from sqlalchemy import select
    from app.models import Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty
    from app.economy import mark_cleared
    from app.security import issue_token

    # Register a fresh account via HTTP so the DB row has all defaults.
    email = f"floor+{_random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    acc_id = r.json()["id"] if "id" in r.json() else None

    # Load the account from DB.
    acc = db_session.scalar(select(Account).where(Account.email == email))
    assert acc is not None

    # Find any LEGENDARY stage in the seeded set.
    leg = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.LEGENDARY).limit(1)
    )
    assert leg is not None, "seed must include LEGENDARY stages"

    # Pre-clear the requires_code chain (LEGENDARY requires NIGHTMARE requires HARD requires NORMAL).
    def _clear_chain(code: str, depth: int = 0) -> None:
        if not code or depth > 4:
            return
        s = db_session.scalar(select(Stage).where(Stage.code == code))
        if s and s.requires_code:
            _clear_chain(s.requires_code, depth + 1)
        mark_cleared(acc, code)

    if leg.requires_code:
        _clear_chain(leg.requires_code)

    db_session.commit()

    # Give the account 5 minimal-power heroes (level 1 commons).
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

    token = issue_token(acc.id, acc.token_version)
    r = client.post(
        "/battles",
        headers={"Authorization": f"Bearer {token}"},
        json={"stage_id": leg.id, "team": hero_ids},
    )
    assert r.status_code == 400, r.text
    body = r.json()
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        assert detail["required"] == 100_000
        assert detail["current"] < 100_000
    else:
        assert "100" in str(detail) or "power" in str(detail).lower()
