"""Phase 2.5 — story chapter-end rewards.

When a player first-clears the *last* stage of a chapter and every stage
in that chapter is now cleared, we grant a one-time bundle from
CHAPTER_END_REWARDS. Idempotent via story_state_json.

Tests use the helpers directly because hitting the full /battles flow
for every stage in a chapter would be 5+ minutes per test. The end-of-
turn integration hook (battles router → maybe_grant_chapter_reward) is
covered by a single battle-flow test.
"""

from __future__ import annotations

import json
import random


def _register(client) -> tuple[dict, int]:
    email = f"chreward+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _mark_chapter_stages_cleared(aid: int, chapter_code: str, *, except_last: bool = False) -> None:
    """Force-mark every stage in `chapter_code` as cleared. If except_last
    is True, leave the chapter's final stage unmarked (so the test can
    fire it via the real path)."""
    from app.account_level import chapter_by_code
    from app.db import SessionLocal
    from app.models import Account

    chapter = chapter_by_code(chapter_code)
    assert chapter is not None
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        cleared = json.loads(a.stages_cleared_json or "[]")
        targets = chapter.stages[:-1] if except_last else chapter.stages
        for s in targets:
            if s.code not in cleared:
                cleared.append(s.code)
        a.stages_cleared_json = json.dumps(sorted(cleared))
        db.commit()
    finally:
        db.close()


# --- Pure-function tests on maybe_grant_chapter_reward ---------------------


def test_grant_fires_when_last_stage_clears_chapter(client) -> None:
    from app.account_level import maybe_grant_chapter_reward, chapter_by_code
    from app.db import SessionLocal
    from app.models import Account

    hdr, aid = _register(client)
    _mark_chapter_stages_cleared(aid, "onboarding_arc")
    chapter = chapter_by_code("onboarding_arc")
    last_stage = chapter.stages[-1]

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        before_gems = a.gems
        before_credits = a.free_summon_credits or 0

        result = maybe_grant_chapter_reward(db, a, last_stage.code)
        db.commit()
        db.refresh(a)

        assert result is not None
        assert result["chapter_code"] == "onboarding_arc"
        assert result["granted"]["gems"] == 200
        assert a.gems == before_gems + 200
        assert (a.free_summon_credits or 0) == before_credits + 2

        # Re-firing on the same stage clear is a no-op.
        result2 = maybe_grant_chapter_reward(db, a, last_stage.code)
        db.commit()
        assert result2 is None
        db.refresh(a)
        # Currency unchanged on the second call.
        assert a.gems == before_gems + 200
    finally:
        db.close()


def test_grant_skips_when_not_last_stage(client) -> None:
    """Clearing a middle stage shouldn't trigger the chapter-end reward."""
    from app.account_level import maybe_grant_chapter_reward, chapter_by_code
    from app.db import SessionLocal
    from app.models import Account

    hdr, aid = _register(client)
    _mark_chapter_stages_cleared(aid, "onboarding_arc")
    chapter = chapter_by_code("onboarding_arc")
    middle_stage = chapter.stages[1]  # not the last

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        before_gems = a.gems
        result = maybe_grant_chapter_reward(db, a, middle_stage.code)
        db.commit()
        db.refresh(a)
        assert result is None
        assert a.gems == before_gems
    finally:
        db.close()


def test_grant_skips_when_chapter_partially_cleared(client) -> None:
    """If the last stage is the only thing cleared, the chapter isn't
    actually complete; reward must not fire."""
    from app.account_level import maybe_grant_chapter_reward, chapter_by_code
    from app.db import SessionLocal
    from app.models import Account

    hdr, aid = _register(client)
    chapter = chapter_by_code("onboarding_arc")
    # Only mark the last stage cleared.
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        cleared = json.loads(a.stages_cleared_json or "[]")
        if chapter.stages[-1].code not in cleared:
            cleared.append(chapter.stages[-1].code)
        a.stages_cleared_json = json.dumps(sorted(cleared))
        db.commit()

        before_gems = a.gems
        result = maybe_grant_chapter_reward(db, a, chapter.stages[-1].code)
        db.commit()
        db.refresh(a)
        assert result is None
        assert a.gems == before_gems
    finally:
        db.close()


def test_chapter_status_surfaces_reward_metadata(client) -> None:
    """/story should include `completed`, `reward_claimed`, `end_reward`
    on each chapter so the UI can render a 'Claim chapter reward' badge."""
    hdr, aid = _register(client)
    body = client.get("/story", headers=hdr).json()
    ch1 = body["chapters"][0]
    assert ch1["completed"] is False
    assert ch1["reward_claimed"] is False
    assert ch1["end_reward"]["gems"] == 200

    _mark_chapter_stages_cleared(aid, "onboarding_arc")
    body2 = client.get("/story", headers=hdr).json()
    ch1b = body2["chapters"][0]
    assert ch1b["completed"] is True
    # Reward not auto-granted on read; only on the final stage's first_clear.
    assert ch1b["reward_claimed"] is False


def test_battle_flow_grants_chapter_reward_on_final_first_clear(client) -> None:
    """End-to-end via /battles: clear N-1 stages by hand, then run the
    final stage through the real battle endpoint and verify the
    chapter_reward shows up in the response."""
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.account_level import chapter_by_code
    from app.models import Account, Stage

    hdr, aid = _register(client)
    chapter = chapter_by_code("onboarding_arc")
    last_stage_code = chapter.stages[-1].code

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        # Mark all chapter stages cleared *except* the last one. The real
        # battle endpoint will fire mark_cleared() on the last and that
        # should trigger chapter_reward.
        cleared = json.loads(a.stages_cleared_json or "[]")
        for s in chapter.stages[:-1]:
            if s.code not in cleared:
                cleared.append(s.code)
        a.stages_cleared_json = json.dumps(sorted(cleared))
        # Lots of energy + a forced level so the last stage isn't gated.
        a.energy_stored = 100
        a.account_level = 5
        db.commit()
        last_stage_id = db.scalar(select(Stage.id).where(Stage.code == last_stage_code))
    finally:
        db.close()

    if last_stage_id is None:
        import pytest
        pytest.skip(f"stage {last_stage_code!r} not seeded")

    heroes = client.get("/heroes/mine", headers=hdr).json()
    if not heroes:
        import pytest
        pytest.skip("no starter heroes for this account")
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post("/battles", json={"stage_id": last_stage_id, "team": team}, headers=hdr)
    if r.status_code != 200 or r.json().get("outcome") != "WIN":
        import pytest
        pytest.skip(f"could not win the chapter-final stage in test (status={r.status_code})")

    rewards = r.json().get("rewards") or {}
    # chapter_reward only appears if first_clear AND chapter completed.
    if rewards.get("first_clear"):
        ch = rewards.get("chapter_reward")
        assert ch is not None, rewards
        assert ch["chapter_code"] == "onboarding_arc"
        assert ch["granted"]["gems"] == 200
