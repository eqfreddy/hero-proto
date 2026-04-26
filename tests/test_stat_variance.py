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
    assert r.status_code == 201, r.text
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


def test_duplicate_summon_rolls_variance(client) -> None:
    """Force a dupe by giving the account enough shards and pulling x10.
    With 35 templates and 10 pulls there's still no guarantee of a dupe
    in any single batch — we retry up to a few times before bailing."""
    hdr, aid = _register(client)
    _set_shards(aid, 10_000)

    saw_dupe_with_variance = False
    for _ in range(10):
        r = client.post("/summon/x10", headers=hdr)
        assert r.status_code == 201, r.text
        # If any of the 10 pulls landed a template the account already
        # owned at the moment of that pull, it should have variance set.
        for entry in r.json():
            v = entry["hero"]["variance_pct"]
            if v:
                # All four stats must be present and within bounds.
                for k in ("hp", "atk", "def", "spd"):
                    assert k in v, v
                    assert -0.10 - 1e-6 <= v[k] <= 0.10 + 1e-6, v
                saw_dupe_with_variance = True
        if saw_dupe_with_variance:
            return
    raise AssertionError("never observed a duplicate summon with variance")


def test_variance_persists_in_db(client) -> None:
    """variance_pct_json round-trips through the DB so battles + later
    /heroes/mine reads see the same numbers."""
    hdr, aid = _register(client)
    _set_shards(aid, 1_000)

    client.post("/summon/x10", headers=hdr)
    client.post("/summon/x10", headers=hdr)  # increase dupe odds
    heroes = client.get("/heroes/mine", headers=hdr).json()
    with_variance = [h for h in heroes if h["variance_pct"]]
    if not with_variance:
        # Bracket — RNG-gated. Skip rather than fail since the previous
        # test already proves variance fires; this one only checks the
        # round-trip when it *does*.
        import pytest
        pytest.skip("no dupes rolled in this seed; round-trip check moot")

    h = with_variance[0]
    from app.db import SessionLocal
    from app.gacha import parse_variance
    from app.models import HeroInstance
    db = SessionLocal()
    try:
        row = db.get(HeroInstance, h["id"])
        assert row is not None
        on_disk = parse_variance(row.variance_pct_json)
        assert on_disk == {k: float(v) for k, v in h["variance_pct"].items()}
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
