"""Phase 2.2 — per-stat variance on duplicate summons.

First copy of a template stays vanilla (variance_pct == {}). Second and
later copies roll a triangular ±10% per-stat offset so dupes are no
longer bit-identical and rolling for an upgrade is a thing.

The variance is set once at creation and never re-rolled — keeps stat
sheets stable across ascensions / sells.
"""

from __future__ import annotations

import json
import random


def _register(client) -> tuple[dict, int]:
    email = f"var+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _set_shards(aid: int, shards: int) -> None:
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.shards = shards
        db.commit()
    finally:
        db.close()


def test_first_copy_has_no_variance(client) -> None:
    """A brand-new account's starter team are all 'first copies' — no
    variance applied. Pulling once and ending up with a brand-new
    template likewise gets no variance."""
    hdr, aid = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    # Starter team: 3 COMMON heroes seeded at register. Dupes within the
    # starter team *are possible* because we pick with replacement, so we
    # can only assert that the FIRST occurrence of each template_id is
    # vanilla.
    seen: set[int] = set()
    for h in heroes:
        if h["template"]["id"] not in seen:
            seen.add(h["template"]["id"])
            assert h["variance_pct"] == {}, h


def test_duplicate_summon_credits_shards_not_variance(client) -> None:
    """Shard remap (2026-05-12): duplicate pulls credit template shards
    and do NOT mint a new HeroInstance, so variance stays locked at the
    first-pull value (vanilla `{}`). Test asserts the new contract:
    `is_duplicate=true`, `shards_granted > 0`, and the response hero is
    the same canonical row across dupes."""
    hdr, aid = _register(client)
    _set_shards(aid, 10_000)

    saw_dupe = False
    canonical_ids: dict[int, int] = {}  # template_id -> hero id
    # Seed canonical_ids from the starter team — those rows aren't
    # surfaced via SummonOut so they'd otherwise appear as KeyErrors
    # when a dupe lands on a starter template.
    for h in client.get("/heroes/mine", headers=hdr).json():
        canonical_ids[h["template"]["id"]] = h["id"]

    for _ in range(20):
        r = client.post("/summon/x10", headers=hdr)
        assert r.status_code == 201, r.text
        for entry in r.json():
            tid = entry["hero"]["template"]["id"]
            hid = entry["hero"]["id"]
            if entry["is_duplicate"]:
                saw_dupe = True
                assert entry["shards_granted"] > 0, entry
                # Variance never re-rolls — stays vanilla {} or whatever
                # the first pull set.
                assert hid == canonical_ids[tid], (entry, canonical_ids)
            else:
                # First pull of this template — variance is locked vanilla.
                assert entry["hero"]["variance_pct"] == {}, entry
                assert entry["shards_granted"] == 0, entry
                canonical_ids[tid] = hid
        if saw_dupe:
            return
    raise AssertionError("never observed a duplicate summon")


def test_variance_persists_in_db(client) -> None:
    """Shard remap (2026-05-12): the variance plumbing stays in place
    even though the gacha no longer rolls fresh values — shard re-roll
    is on the post-remap roadmap. This test forges a non-vanilla
    variance via direct DB write to prove the round-trip still works."""
    hdr, aid = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    assert heroes, "starter team should seed heroes"
    hid = heroes[0]["id"]

    from app.db import SessionLocal
    from app.gacha import parse_variance, serialize_variance
    from app.models import HeroInstance
    forged = {"hp": 0.07, "atk": -0.04, "def": 0.01, "spd": 0.10}
    db = SessionLocal()
    try:
        row = db.get(HeroInstance, hid)
        row.variance_pct_json = serialize_variance(forged)
        db.commit()
    finally:
        db.close()

    heroes_after = client.get("/heroes/mine", headers=hdr).json()
    hero = next(h for h in heroes_after if h["id"] == hid)
    assert hero["variance_pct"] == forged, hero

    db = SessionLocal()
    try:
        row = db.get(HeroInstance, hid)
        assert parse_variance(row.variance_pct_json) == forged
    finally:
        db.close()


def test_variance_serialize_parse_roundtrip() -> None:
    """Pure-function check: serialize → parse is identity within float
    precision; out-of-bounds inputs get clamped on parse."""
    from app.gacha import parse_variance, serialize_variance

    pct = {"hp": 0.05, "atk": -0.07, "def": 0.0, "spd": 0.10}
    blob = serialize_variance(pct)
    assert json.loads(blob) == pct
    assert parse_variance(blob) == pct

    # Clamp on parse — a legacy / hand-edited row outside the bound is
    # squeezed back into [-0.10, 0.10] rather than silently scaling 50%.
    out_of_bounds = json.dumps({"hp": 0.5, "atk": -0.99, "def": 0.0, "spd": 0.0})
    parsed = parse_variance(out_of_bounds)
    assert parsed["hp"] == 0.10
    assert parsed["atk"] == -0.10

    # Empty / malformed → {}.
    assert parse_variance(None) == {}
    assert parse_variance("") == {}
    assert parse_variance("not-json") == {}
    assert parse_variance("[]") == {}


def test_variance_changes_combat_stats() -> None:
    """build_unit with variance applies the offset before gear, scaling
    the base level/star value."""
    from app.combat import build_unit
    from app.models import Role

    def _b(variance: dict | None) -> tuple[int, int, int, int]:
        u = build_unit(
            uid="A0", side="A", name="Test", role=Role.ATK,
            level=10, base_hp=1000, base_atk=100, base_def=80, base_spd=50,
            basic_mult=1.0, special=None, special_cooldown=0,
            variance_pct=variance,
        )
        return u.max_hp, u.atk, u.def_, u.spd

    base = _b(None)
    bumped = _b({"hp": 0.10, "atk": 0.10, "def": 0.10, "spd": 0.10})
    nerfed = _b({"hp": -0.10, "atk": -0.10, "def": -0.10, "spd": -0.10})

    for nominal, plus, minus in zip(base, bumped, nerfed):
        assert plus > nominal > minus, (nominal, plus, minus)
