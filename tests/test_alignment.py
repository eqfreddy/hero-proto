"""Phase 3.5 — Alignment Fork tests.

Covers:
- Cannot choose alignment before level 50
- Can choose RESISTANCE at level 50
- Can choose CORP_GREED at level 50
- Cannot choose twice (409)
- Alignment chapters appear only for correct faction
- Chapter-end hero grant creates HeroInstance
- ME endpoint returns faction and alignment_chosen_at
"""

from __future__ import annotations

import json
import random

import pytest


def _register(client) -> tuple[dict, int]:
    email = f"align+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _set_level(aid: int, level: int) -> None:
    from app.db import SessionLocal
    from app.models import Account

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.account_level = level
        db.commit()
    finally:
        db.close()


def _mark_all_stages_cleared(aid: int, chapter_code: str) -> None:
    from app.account_level import chapter_by_code
    from app.db import SessionLocal
    from app.models import Account

    chapter = chapter_by_code(chapter_code)
    assert chapter is not None
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        cleared = json.loads(a.stages_cleared_json or "[]")
        for s in chapter.stages:
            if s.code not in cleared:
                cleared.append(s.code)
        a.stages_cleared_json = json.dumps(sorted(cleared))
        db.commit()
    finally:
        db.close()


# --- Alignment choice endpoint -----------------------------------------------


def test_cannot_choose_before_level_50(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 49)
    r = client.post("/story/alignment", json={"alignment": "RESISTANCE"}, headers=hdr)
    assert r.status_code == 403, r.text


def test_choose_resistance_at_level_50(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)

    r = client.post("/story/alignment", json={"alignment": "RESISTANCE"}, headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["faction"] == "RESISTANCE"
    assert data["alignment_chosen_at"] is not None

    me = client.get("/me", headers=hdr).json()
    assert me["faction"] == "RESISTANCE"
    assert me["alignment_chosen_at"] is not None


def test_choose_corp_greed_at_level_50(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)

    r = client.post("/story/alignment", json={"alignment": "CORP_GREED"}, headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["faction"] == "CORP_GREED"

    me = client.get("/me", headers=hdr).json()
    assert me["faction"] == "CORP_GREED"


def test_invalid_alignment_rejected(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)
    r = client.post("/story/alignment", json={"alignment": "EXILE"}, headers=hdr)
    assert r.status_code == 400, r.text


def test_cannot_choose_twice(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)

    r1 = client.post("/story/alignment", json={"alignment": "RESISTANCE"}, headers=hdr)
    assert r1.status_code == 200, r1.text

    # Second call — must 409 regardless of chosen value.
    r2 = client.post("/story/alignment", json={"alignment": "CORP_GREED"}, headers=hdr)
    assert r2.status_code == 409, r2.text

    r3 = client.post("/story/alignment", json={"alignment": "RESISTANCE"}, headers=hdr)
    assert r3.status_code == 409, r3.text


# --- Story chapter visibility ------------------------------------------------


def test_exile_sees_no_alignment_chapters(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)  # level unlocked but no alignment chosen

    r = client.get("/story", headers=hdr)
    assert r.status_code == 200, r.text
    chapters = r.json()["chapters"]
    codes = [ch["code"] for ch in chapters]
    assert "resistance_arc" not in codes
    assert "corpgreed_arc" not in codes


def test_resistance_sees_only_resistance_chapter(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)
    client.post("/story/alignment", json={"alignment": "RESISTANCE"}, headers=hdr)

    r = client.get("/story", headers=hdr)
    chapters = r.json()["chapters"]
    codes = [ch["code"] for ch in chapters]
    assert "resistance_arc" in codes
    assert "corpgreed_arc" not in codes


def test_corp_greed_sees_only_corpgreed_chapter(client) -> None:
    hdr, aid = _register(client)
    _set_level(aid, 50)
    client.post("/story/alignment", json={"alignment": "CORP_GREED"}, headers=hdr)

    r = client.get("/story", headers=hdr)
    chapters = r.json()["chapters"]
    codes = [ch["code"] for ch in chapters]
    assert "corpgreed_arc" in codes
    assert "resistance_arc" not in codes


# --- Alignment chapter hero grant --------------------------------------------


def test_alignment_chapter_complete_grants_hero(client) -> None:
    from app.account_level import maybe_grant_chapter_reward, chapter_by_code
    from app.db import SessionLocal
    from app.models import Account, HeroInstance

    hdr, aid = _register(client)
    _set_level(aid, 50)
    client.post("/story/alignment", json={"alignment": "RESISTANCE"}, headers=hdr)

    # Mark all stages in resistance_arc cleared.
    _mark_all_stages_cleared(aid, "resistance_arc")

    chapter = chapter_by_code("resistance_arc")
    assert chapter is not None
    last_stage = chapter.stages[-1]

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        before_gems = a.gems

        result = maybe_grant_chapter_reward(db, a, last_stage.code)
        db.commit()
        db.refresh(a)

        assert result is not None, "chapter reward should fire"
        assert result["chapter_code"] == "resistance_arc"
        assert result["hero_granted"] == "the_whistleblower"
        assert a.gems > before_gems  # currency also granted

        # Hero instance must exist.
        from app.models import HeroTemplate
        tmpl = db.query(HeroTemplate).filter_by(code="the_whistleblower").first()
        if tmpl is not None:
            inst = (
                db.query(HeroInstance)
                .filter_by(account_id=aid, template_id=tmpl.id)
                .first()
            )
            assert inst is not None, "HeroInstance should have been created"

        # Idempotency: second call returns None, no second hero.
        result2 = maybe_grant_chapter_reward(db, a, last_stage.code)
        db.commit()
        assert result2 is None
    finally:
        db.close()


def test_corp_greed_chapter_complete_grants_hero(client) -> None:
    from app.account_level import maybe_grant_chapter_reward, chapter_by_code
    from app.db import SessionLocal
    from app.models import Account, HeroInstance

    hdr, aid = _register(client)
    _set_level(aid, 50)
    client.post("/story/alignment", json={"alignment": "CORP_GREED"}, headers=hdr)

    _mark_all_stages_cleared(aid, "corpgreed_arc")

    chapter = chapter_by_code("corpgreed_arc")
    assert chapter is not None
    last_stage = chapter.stages[-1]

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        result = maybe_grant_chapter_reward(db, a, last_stage.code)
        db.commit()

        assert result is not None
        assert result["hero_granted"] == "the_successor"
    finally:
        db.close()


# --- ME endpoint faction fields ----------------------------------------------


def test_me_returns_faction_and_alignment_chosen_at(client) -> None:
    hdr, aid = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    assert me_before["faction"] == "EXILE"
    assert me_before["alignment_chosen_at"] is None

    _set_level(aid, 50)
    client.post("/story/alignment", json={"alignment": "CORP_GREED"}, headers=hdr)

    me_after = client.get("/me", headers=hdr).json()
    assert me_after["faction"] == "CORP_GREED"
    assert me_after["alignment_chosen_at"] is not None
