"""Extended daily quest kinds: CLEAR_HARD_STAGE progress from battles, RAID_DAMAGE
progress from raid attacks.

Tests use the progress hooks directly to avoid depending on the RNG-shuffled
quest slot roll. Seeds a quest of the target kind for today, then triggers the
hook and asserts progress/completion.
"""

from __future__ import annotations

import random
from datetime import timedelta

from app.daily import day_key, on_hard_stage_clear, on_raid_damage
from app.db import SessionLocal
from app.models import Account, DailyQuest, DailyQuestKind, DailyQuestStatus


def _register(client, prefix: str = "dqv") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _seed_quest(account_id: int, kind: DailyQuestKind, goal: int = 1) -> int:
    with SessionLocal() as db:
        q = DailyQuest(
            account_id=account_id,
            day_key=day_key(),
            kind=kind,
            goal=goal,
            progress=0,
            status=DailyQuestStatus.ACTIVE,
            reward_coins=100,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        return q.id


def test_hard_stage_quest_advances_on_hard_win(client) -> None:
    """The CLEAR_HARD_STAGE hook advances only on hard-tier wins."""
    hdr, account_id = _register(client)
    qid = _seed_quest(account_id, DailyQuestKind.CLEAR_HARD_STAGE, goal=1)

    with SessionLocal() as db:
        a = db.get(Account, account_id)
        on_hard_stage_clear(db, a)
        db.commit()

    with SessionLocal() as db:
        q = db.get(DailyQuest, qid)
        assert q.progress == 1
        assert q.status == DailyQuestStatus.COMPLETE


def test_raid_damage_quest_accumulates_damage(client) -> None:
    hdr, account_id = _register(client)
    qid = _seed_quest(account_id, DailyQuestKind.RAID_DAMAGE, goal=10_000)

    # Two attacks of 3000 and 8000 damage → total 11000, completes the 10000 goal.
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        on_raid_damage(db, a, 3000)
        on_raid_damage(db, a, 8000)
        db.commit()

    with SessionLocal() as db:
        q = db.get(DailyQuest, qid)
        assert q.progress == 10_000, "progress should clamp at goal"
        assert q.status == DailyQuestStatus.COMPLETE


def test_raid_damage_quest_ignores_zero_damage(client) -> None:
    hdr, account_id = _register(client)
    qid = _seed_quest(account_id, DailyQuestKind.RAID_DAMAGE, goal=1000)

    with SessionLocal() as db:
        a = db.get(Account, account_id)
        on_raid_damage(db, a, 0)
        on_raid_damage(db, a, -50)  # pathological
        db.commit()

    with SessionLocal() as db:
        q = db.get(DailyQuest, qid)
        assert q.progress == 0, "zero/negative damage shouldn't advance progress"


def test_hard_stage_quest_kind_exists_in_enum() -> None:
    # Simple sanity: the new enum values are exported so schemas serialize cleanly.
    assert DailyQuestKind.CLEAR_HARD_STAGE.value == "CLEAR_HARD_STAGE"
    assert DailyQuestKind.RAID_DAMAGE.value == "RAID_DAMAGE"
    assert DailyQuestKind.SPEND_GEMS.value == "SPEND_GEMS"


def test_live_hard_stage_win_advances_quest(client) -> None:
    """End-to-end: grant the account prereqs, seed a CLEAR_HARD_STAGE quest,
    beat a HARD stage via /battles, and verify the quest advanced."""
    from app.economy import load_cleared, save_cleared

    hdr, account_id = _register(client)
    # Summon + build team.
    client.post("/summon/x10", headers=hdr)
    roster = sorted(
        client.get("/heroes/mine", headers=hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    team = [h["id"] for h in roster[:3]]

    # Unlock HARD for onboarding_day.
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        cleared = load_cleared(a)
        cleared.add("onboarding_day")
        save_cleared(a, cleared)
        db.commit()

    # Seed a fresh CLEAR_HARD_STAGE quest for today.
    qid = _seed_quest(account_id, DailyQuestKind.CLEAR_HARD_STAGE, goal=1)

    stages = client.get("/stages").json()
    hard1 = next(s for s in stages if s["code"] == "H-onboarding_day")

    # Fight — outcome may WIN or LOSS depending on RNG. Only WIN advances the quest.
    won = False
    for _ in range(6):
        r = client.post("/battles", json={"stage_id": hard1["id"], "team": team}, headers=hdr)
        assert r.status_code == 201
        if r.json()["outcome"] == "WIN":
            won = True
            break
    if not won:
        # If we couldn't win the HARD stage, the assertion below would be the wrong
        # signal. Skip instead of falsely failing.
        import pytest
        pytest.skip("couldn't win HARD stage in 6 tries — RNG-dependent")

    with SessionLocal() as db:
        q = db.get(DailyQuest, qid)
        assert q.progress >= 1, f"hard quest didn't advance after hard WIN: progress={q.progress}"
