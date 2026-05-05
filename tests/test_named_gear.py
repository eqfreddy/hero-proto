"""Phase 4 — named legendary gear (Veteran IT armor set).

Each story chapter completion grants a single named piece. The level-50
alignment fork grants the LEGS piece universally. All grants are
idempotent.
"""

from __future__ import annotations

import json
import random


def _register(client) -> tuple[dict, int]:
    email = f"namedgear+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _mark_chapter_stages_cleared(aid: int, chapter_code: str) -> None:
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


def test_named_gear_catalog_has_all_six_armor_slots() -> None:
    """The Veteran IT set should cover every armor slot once."""
    from app.named_gear import NAMED_GEAR
    from app.models import GearSlot

    armor_slots = {GearSlot.HEAD, GearSlot.CHEST, GearSlot.HANDS,
                   GearSlot.WRIST, GearSlot.LEGS, GearSlot.FEET}
    catalog_slots = {spec.slot for spec in NAMED_GEAR.values()}
    assert catalog_slots == armor_slots, f"expected {armor_slots}, got {catalog_slots}"


def test_named_gear_pieces_are_legendary() -> None:
    """All story-reward pieces are LEGENDARY tier."""
    from app.models import GearRarity
    from app.named_gear import NAMED_GEAR
    for code, spec in NAMED_GEAR.items():
        assert spec.rarity == GearRarity.LEGENDARY, f"{code} should be LEGENDARY"


def test_grant_named_gear_idempotent(client) -> None:
    """Granting the same named piece twice produces only one row."""
    from app.db import SessionLocal
    from app.models import Account, Gear
    from app.named_gear import grant_named_gear
    from sqlalchemy import select

    hdr, aid = _register(client)
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        first = grant_named_gear(db, a, "help_desk_headset")
        second = grant_named_gear(db, a, "help_desk_headset")
        db.commit()

        assert first is True
        assert second is False

        rows = db.scalars(
            select(Gear).where(Gear.account_id == aid, Gear.name == "Help Desk Headset")
        ).all()
        assert len(rows) == 1
        g = rows[0]
        assert g.flavor is not None
        assert g.rarity == "LEGENDARY"
    finally:
        db.close()


def test_chapter_completion_grants_named_gear(client) -> None:
    """Clearing the last stage of a chapter grants the matched named piece."""
    from app.account_level import chapter_by_code, maybe_grant_chapter_reward
    from app.db import SessionLocal
    from app.models import Account, Gear
    from sqlalchemy import select

    hdr, aid = _register(client)
    _mark_chapter_stages_cleared(aid, "middle_management_arc")

    chapter = chapter_by_code("middle_management_arc")
    last = chapter.stages[-1]

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        result = maybe_grant_chapter_reward(db, a, last.code)
        db.commit()

        assert result is not None
        assert result["gear_granted"] is not None
        assert result["gear_granted"]["code"] == "power_suit_jacket"
        assert result["gear_granted"]["slot"] == "CHEST"

        rows = db.scalars(
            select(Gear).where(Gear.account_id == aid, Gear.name == "Power-Suit Jacket")
        ).all()
        assert len(rows) == 1
    finally:
        db.close()


def test_chapter_completion_idempotent_on_gear(client) -> None:
    """Re-firing the chapter clear hook does not duplicate the named gear."""
    from app.account_level import chapter_by_code, maybe_grant_chapter_reward
    from app.db import SessionLocal
    from app.models import Account, Gear
    from sqlalchemy import select

    hdr, aid = _register(client)
    _mark_chapter_stages_cleared(aid, "onboarding_arc")
    chapter = chapter_by_code("onboarding_arc")
    last = chapter.stages[-1]

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        maybe_grant_chapter_reward(db, a, last.code)
        db.commit()
        # Reset the claim flag to force a re-grant attempt — simulates a bug
        # where the idempotency layer above missed.
        from app.account_level import _state, _save
        s = _state(a)
        s.pop("chapter_rewards_claimed", None)
        _save(a, s)
        db.commit()

        result = maybe_grant_chapter_reward(db, a, last.code)
        db.commit()
        # Currency / chapter reward fires again (we cleared the flag), but
        # gear_granted is None because grant_named_gear is name-keyed
        # idempotent at the DB layer.
        assert result is not None
        assert result["gear_granted"] is None

        rows = db.scalars(
            select(Gear).where(Gear.account_id == aid, Gear.name == "Help Desk Headset")
        ).all()
        assert len(rows) == 1
    finally:
        db.close()


def test_alignment_fork_grants_legs_piece(client) -> None:
    """Picking an alignment at level 50 should drop the Cargo Pants in inventory."""
    from app.db import SessionLocal
    from app.models import Account, Gear
    from sqlalchemy import select

    hdr, aid = _register(client)
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.account_level = 50
        db.commit()
    finally:
        db.close()

    r = client.post("/story/alignment", headers=hdr, json={"alignment": "RESISTANCE"})
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        rows = db.scalars(
            select(Gear).where(Gear.account_id == aid, Gear.name == "Cargo Pants of Many Tabs")
        ).all()
        assert len(rows) == 1
        g = rows[0]
        assert g.slot == "LEGS"
        assert g.rarity == "LEGENDARY"
    finally:
        db.close()


def test_named_gear_appears_in_gear_mine_with_name_and_flavor(client) -> None:
    """GET /gear/mine surfaces the name + flavor fields."""
    from app.db import SessionLocal
    from app.models import Account
    from app.named_gear import grant_named_gear

    hdr, aid = _register(client)
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        grant_named_gear(db, a, "all_terrain_loafers")
        db.commit()
    finally:
        db.close()

    r = client.get("/gear/mine", headers=hdr)
    assert r.status_code == 200
    items = r.json()
    named = [g for g in items if g.get("name") == "All-Terrain Loafers"]
    assert len(named) == 1
    g = named[0]
    assert g["slot"] == "FEET"
    assert g["rarity"] == "LEGENDARY"
    assert g["flavor"] is not None
    assert "Italian leather" in g["flavor"]


def test_old_gear_slot_names_no_longer_in_enum() -> None:
    """HELMET / ARMOR / BOOTS were renamed to HEAD / CHEST / FEET."""
    from app.models import GearSlot
    values = {s.value for s in GearSlot}
    assert "HEAD" in values
    assert "CHEST" in values
    assert "FEET" in values
    assert "HANDS" in values
    assert "WRIST" in values
    assert "LEGS" in values
    assert "HELMET" not in values
    assert "ARMOR" not in values
    assert "BOOTS" not in values
