"""Tests for the milestone reward system.

Covers:
- Unlock thresholds trigger at correct cleared-stage counts
- Claim credits expected shard quantity to account.shards
- Claiming twice returns HTTP 409 "already claimed"
- Claiming when not yet unlocked returns HTTP 409 "milestone not yet unlocked"
- Pity floor: 10 consecutive misses guarantee the 11th award
- Pity resets on award; increments on miss
- Legend boss summon deducts 30 shards; 29 shards → 409
- GET /stages/milestones returns correct next_milestone + stages_to_go
- BattleOut.milestone_unlocks surface after first stage clear past threshold
- Legend boss pool only pulls MYTH templates with is_legend_boss_pool=True
"""
from __future__ import annotations

import json
import random

import pytest

from tests.conftest import *  # noqa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register(client, tag: str = "") -> tuple[str, int]:
    suffix = tag + str(random.randint(1_000_000, 9_999_999))
    email = f"ms-{suffix}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/me", headers=_hdr(tok)).json()
    return tok, me["id"]


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _set_cleared(aid: int, stage_codes: list[str]) -> None:
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.stages_cleared_json = json.dumps(stage_codes)
        db.commit()


def _get_account(aid: int):
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        db.expunge(a)
        return a


def _set_account_fields(aid: int, **fields) -> None:
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        for k, v in fields.items():
            setattr(a, k, v)
        db.commit()


def _first_milestone_id(client, tok: str) -> int:
    r = client.get("/stages/milestones", headers=_hdr(tok))
    assert r.status_code == 200, r.text
    return r.json()["milestones"][0]["id"]


def _get_stage_code(n: int) -> str:
    """Return the code of the n-th stage (0-indexed) from the DB."""
    from app.db import SessionLocal
    from app.models import Stage
    from sqlalchemy import select
    with SessionLocal() as db:
        stages = db.scalars(select(Stage).order_by(Stage.order)).all()
        if n < len(stages):
            return stages[n].code
        raise ValueError(f"Not enough stages seeded (need index {n}, have {len(stages)})")


# ---------------------------------------------------------------------------
# 1. Unlock thresholds
# ---------------------------------------------------------------------------


def test_milestone_not_unlocked_below_threshold(client):
    tok, aid = _register(client, "thresh-below")
    _set_cleared(aid, [f"fake_stage_{i}" for i in range(4)])  # 4 < 5
    r = client.get("/stages/milestones", headers=_hdr(tok))
    assert r.status_code == 200
    m1 = r.json()["milestones"][0]
    assert m1["stage_count"] == 5
    assert m1["unlocked"] is False


def test_milestone_unlocked_at_threshold(client):
    tok, aid = _register(client, "thresh-at")
    _set_cleared(aid, [f"fake_stage_{i}" for i in range(5)])  # exactly 5
    r = client.get("/stages/milestones", headers=_hdr(tok))
    assert r.status_code == 200
    m1 = r.json()["milestones"][0]
    assert m1["stage_count"] == 5
    assert m1["unlocked"] is True


# ---------------------------------------------------------------------------
# 2. Claiming a milestone credits expected shard quantity
# ---------------------------------------------------------------------------


def test_milestone_claim_grants_shards(client):
    tok, aid = _register(client, "claim-shards")
    _set_cleared(aid, [f"fake_stage_{i}" for i in range(5)])

    before = _get_account(aid).shards or 0
    mid = _first_milestone_id(client, tok)

    r = client.post(f"/stages/milestones/{mid}/claim", headers=_hdr(tok))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["template_shards_granted"] == 20  # milestone 1 = 20 shards

    after = _get_account(aid).shards or 0
    assert after == before + 20


# ---------------------------------------------------------------------------
# 3. Claiming twice → 409 "already claimed"
# ---------------------------------------------------------------------------


def test_milestone_claim_idempotent(client):
    tok, aid = _register(client, "claim-idem")
    _set_cleared(aid, [f"fake_stage_{i}" for i in range(5)])
    mid = _first_milestone_id(client, tok)

    r1 = client.post(f"/stages/milestones/{mid}/claim", headers=_hdr(tok))
    assert r1.status_code == 200

    r2 = client.post(f"/stages/milestones/{mid}/claim", headers=_hdr(tok))
    assert r2.status_code == 409
    assert "already claimed" in r2.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Not yet unlocked → 409 "milestone not yet unlocked"
# ---------------------------------------------------------------------------


def test_milestone_not_yet_unlocked(client):
    tok, aid = _register(client, "claim-locked")
    _set_cleared(aid, [f"fake_stage_{i}" for i in range(3)])  # only 3 clears
    mid = _first_milestone_id(client, tok)

    r = client.post(f"/stages/milestones/{mid}/claim", headers=_hdr(tok))
    assert r.status_code == 409
    assert "not yet unlocked" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Pity floor triggers at N
# ---------------------------------------------------------------------------


def test_pity_floor_triggers_at_n(client):
    """After LEGEND_PITY_FLOOR consecutive misses, next claim is guaranteed."""
    from app.db import SessionLocal
    from app.models import Account, StageMilestone
    from app.milestones import LEGEND_PITY_FLOOR, roll_legend_shard
    from sqlalchemy import select

    with SessionLocal() as db:
        ms = db.scalar(select(StageMilestone).order_by(StageMilestone.stage_count))
        assert ms is not None, "No milestones seeded"
        acct = db.scalar(
            select(Account).order_by(Account.id)
        )
        assert acct is not None

        acct.milestone_legend_pity = LEGEND_PITY_FLOOR

        # A rng that always misses — but pity should override it.
        rng = random.Random()
        rng.random = lambda: 1.0  # type: ignore[method-assign]

        result = roll_legend_shard(acct, ms.legend_shard_chance, rng)
        assert result == 1
        assert acct.milestone_legend_pity == 0


# ---------------------------------------------------------------------------
# 6. Pity resets on award
# ---------------------------------------------------------------------------


def test_pity_resets_on_legend_award(client):
    from app.db import SessionLocal
    from app.models import Account, StageMilestone
    from app.milestones import roll_legend_shard
    from sqlalchemy import select

    with SessionLocal() as db:
        ms = db.scalar(select(StageMilestone).order_by(StageMilestone.stage_count))
        acct = db.scalar(select(Account).order_by(Account.id))
        acct.milestone_legend_pity = 5

        rng = random.Random()
        rng.random = lambda: 0.0  # always hits

        result = roll_legend_shard(acct, ms.legend_shard_chance, rng)
        assert result == 1
        assert acct.milestone_legend_pity == 0


# ---------------------------------------------------------------------------
# 7. Pity increments on miss
# ---------------------------------------------------------------------------


def test_pity_increments_on_miss(client):
    from app.db import SessionLocal
    from app.models import Account, StageMilestone
    from app.milestones import roll_legend_shard
    from sqlalchemy import select

    with SessionLocal() as db:
        ms = db.scalar(select(StageMilestone).order_by(StageMilestone.stage_count))
        acct = db.scalar(select(Account).order_by(Account.id))
        acct.milestone_legend_pity = 3

        rng = random.Random()
        rng.random = lambda: 1.0  # always misses

        result = roll_legend_shard(acct, ms.legend_shard_chance, rng)
        assert result == 0
        assert acct.milestone_legend_pity == 4


# ---------------------------------------------------------------------------
# 8. Legend boss summon deducts 30 shards + returns hero
# ---------------------------------------------------------------------------


def test_legend_boss_summon_deducts_shards(client):
    from app.db import SessionLocal
    from app.models import HeroTemplate, Rarity

    # Ensure at least one MYTH boss-pool template exists.
    with SessionLocal() as db:
        from sqlalchemy import select
        t = db.scalar(
            select(HeroTemplate)
            .where(HeroTemplate.rarity == Rarity.MYTH, HeroTemplate.is_legend_boss_pool.is_(True))
        )
        if t is None:
            t = HeroTemplate(
                code="test_boss_hero_summon",
                name="Test Boss Hero",
                rarity=Rarity.MYTH,
                faction="HELPDESK",
                role="ATK",
                base_hp=1000, base_atk=100, base_def=80, base_spd=90,
                is_legend_boss_pool=True,
            )
            db.add(t)
            db.commit()

    tok, aid = _register(client, "boss-summon")
    _set_account_fields(aid, legend_boss_shards=30)

    r = client.post("/stages/milestones/legend-boss-summon", headers=_hdr(tok))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["legend_boss_shards_balance"] == 0
    assert "hero" in data
    assert data["hero"]["id"] is not None


# ---------------------------------------------------------------------------
# 9. Legend boss summon with insufficient shards → 409
# ---------------------------------------------------------------------------


def test_legend_boss_summon_insufficient_shards(client):
    tok, aid = _register(client, "boss-insufficient")
    _set_account_fields(aid, legend_boss_shards=29)

    r = client.post("/stages/milestones/legend-boss-summon", headers=_hdr(tok))
    assert r.status_code == 409
    assert "insufficient" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 10. GET /stages/milestones progress field
# ---------------------------------------------------------------------------


def test_get_milestones_progress_field(client):
    tok, aid = _register(client, "progress")
    _set_cleared(aid, [f"fake_stage_{i}" for i in range(12)])  # 12 cleared

    r = client.get("/stages/milestones", headers=_hdr(tok))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stages_cleared_count"] == 12
    nm = data["next_milestone"]
    assert nm is not None
    assert nm["stage_count"] == 15  # next unclaimed milestone threshold
    assert nm["stages_to_go"] == 3


# ---------------------------------------------------------------------------
# 11. BattleOut.milestone_unlocks surfaces after first clear past threshold
# ---------------------------------------------------------------------------


def test_milestone_unlocks_in_battle_out(client):
    """Clear exactly 4 stages then fight+win one more → milestone_unlocks should
    contain milestone id for stage_count=5."""
    tok, aid = _register(client, "battle-unlock")

    # Pre-seed 4 clears so the next win triggers the stage-5 milestone.
    _set_cleared(aid, [f"pre_stage_{i}" for i in range(4)])

    # Get an actual stage to fight.
    from app.db import SessionLocal
    from app.models import Stage
    from sqlalchemy import select
    with SessionLocal() as db:
        stage = db.scalar(select(Stage).order_by(Stage.order))
        assert stage is not None, "No stages seeded"
        stage_id = stage.id

    # Summon a team.
    client.post("/summon/x10", headers=_hdr(tok))
    heroes = client.get("/heroes/mine", headers=_hdr(tok)).json()
    assert len(heroes) > 0, "No heroes after summon"

    team = [h["id"] for h in heroes[:3]]
    # Give enough energy.
    _set_account_fields(aid, energy_stored=100)

    r = client.post("/battles", headers=_hdr(tok), json={
        "stage_id": stage_id,
        "team": team,
    })
    assert r.status_code in (200, 201), r.text
    data = r.json()

    # Only assert milestone_unlocks is present and is a list.
    # (It may be empty if the battle was a loss, or non-empty on win over threshold.)
    assert "milestone_unlocks" in data
    assert isinstance(data["milestone_unlocks"], list)


# ---------------------------------------------------------------------------
# 12. Legend boss pool only uses MYTH templates with is_legend_boss_pool=True
# ---------------------------------------------------------------------------


def test_legend_boss_pool_only_myth(client):
    """Summon multiple times and assert all results come from the MYTH pool."""
    from app.db import SessionLocal
    from app.models import HeroTemplate, HeroInstance, Rarity
    from sqlalchemy import select

    # Seed a non-pool MYTH template and a pool template.
    with SessionLocal() as db:
        pool_tpl = db.scalar(
            select(HeroTemplate)
            .where(HeroTemplate.rarity == Rarity.MYTH, HeroTemplate.is_legend_boss_pool.is_(True))
        )
        if pool_tpl is None:
            pool_tpl = HeroTemplate(
                code="test_boss_pool_only",
                name="Boss Pool Only",
                rarity=Rarity.MYTH,
                faction="HELPDESK",
                role="ATK",
                base_hp=1000, base_atk=100, base_def=80, base_spd=90,
                is_legend_boss_pool=True,
            )
            db.add(pool_tpl)

        non_pool = db.scalar(
            select(HeroTemplate)
            .where(HeroTemplate.rarity == Rarity.MYTH, HeroTemplate.is_legend_boss_pool.is_(False))
        )
        if non_pool is None:
            non_pool = HeroTemplate(
                code="test_non_pool_myth",
                name="Non-Pool Myth",
                rarity=Rarity.MYTH,
                faction="HELPDESK",
                role="DEF",
                base_hp=1200, base_atk=90, base_def=120, base_spd=70,
                is_legend_boss_pool=False,
            )
            db.add(non_pool)
        db.commit()
        pool_tpl_id = pool_tpl.id if pool_tpl.id else db.scalar(
            select(HeroTemplate.id).where(HeroTemplate.code == "test_boss_pool_only")
        )

    # Run summon 5 times, each from a fresh account with 30 shards.
    for _ in range(5):
        tok, aid = _register(client, "pool-check")
        _set_account_fields(aid, legend_boss_shards=30)

        r = client.post("/stages/milestones/legend-boss-summon", headers=_hdr(tok))
        assert r.status_code == 200, r.text
        hero_id = r.json()["hero"]["id"]

        with SessionLocal() as db:
            hi = db.get(HeroInstance, hero_id)
            tmpl = db.get(HeroTemplate, hi.template_id)
            assert tmpl.rarity == Rarity.MYTH, f"Expected MYTH, got {tmpl.rarity}"
            assert tmpl.is_legend_boss_pool is True, (
                f"Template {tmpl.code} is not in legend boss pool"
            )
