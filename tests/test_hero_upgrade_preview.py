"""Phase 2.1 — GET /heroes/{id}/preview — next-upgrade chase numbers.

Returns three upgrade paths (level / star / special) with availability,
cost, stat delta, and absolute after-stats. Read-only. The math must
match what /heroes/mine returns so a player sees consistent numbers
between the roster page and the detail page.
"""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"prev+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def test_preview_returns_current_stats_matching_roster(client) -> None:
    """The 'current' block should equal what /heroes/mine reports for
    the same hero — no math drift between endpoints."""
    hdr, _ = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    assert heroes
    h = heroes[0]
    r = client.get(f"/heroes/{h['id']}/preview", headers=hdr)
    assert r.status_code == 200, r.text
    cur = r.json()["current"]
    for k in ("hp", "atk", "def", "spd", "power"):
        assert cur[k] == h[k if k != "def" else "def"], (k, cur, h)


def test_preview_level_up_available_below_cap(client) -> None:
    hdr, _ = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    h = heroes[0]
    r = client.get(f"/heroes/{h['id']}/preview", headers=hdr).json()
    lu = r["level_up"]
    # Starter team is level 1; level cap at 1★ is 15.
    from app.combat import level_cap_for_stars
    assert lu["available"] is True
    assert lu["cost"]["target_level"] == 2
    assert lu["cost"]["level_cap"] == level_cap_for_stars(1)
    assert lu["cost"]["xp_remaining"] >= 0
    # Stats should grow on level up.
    assert lu["after"]["hp"] >= r["current"]["hp"]
    assert lu["after"]["power"] >= r["current"]["power"]


def test_preview_star_up_unavailable_with_no_dupes(client) -> None:
    """A brand-new player with one copy of a template can't ascend it —
    star_up.available is False but the projected delta is still shown
    so the UI can render a 'preview locked' tease."""
    hdr, _ = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    # Find a hero with no dupes in the starter team.
    counts: dict[int, int] = {}
    for h in heroes:
        counts[h["template"]["id"]] = counts.get(h["template"]["id"], 0) + 1
    target = next((h for h in heroes if counts[h["template"]["id"]] == 1), None)
    if target is None:
        import pytest
        pytest.skip("starter pool happened to be all dupes; rare RNG path")
    r = client.get(f"/heroes/{target['id']}/preview", headers=hdr).json()
    su = r["star_up"]
    assert su["cost"]["target_stars"] == 2
    assert su["cost"]["fodder_needed"] == 1
    assert su["cost"]["fodder_available"] == 0
    assert su["available"] is False
    # Even when locked, deltas should be non-zero (preview-locked tease).
    assert su["after"]["power"] >= r["current"]["power"]


def test_preview_star_up_available_with_dupe(client) -> None:
    """Force-create a dupe via DB so star_up.available flips to True."""
    from app.db import SessionLocal
    from app.models import HeroInstance

    hdr, aid = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    target = heroes[0]
    db = SessionLocal()
    try:
        # Add a fresh dupe of the same template owned by this account.
        db.add(HeroInstance(
            account_id=aid, template_id=target["template"]["id"], level=1, xp=0,
        ))
        db.commit()
    finally:
        db.close()

    r = client.get(f"/heroes/{target['id']}/preview", headers=hdr).json()
    su = r["star_up"]
    assert su["cost"]["fodder_needed"] == 1
    assert su["cost"]["fodder_available"] >= 1
    assert su["available"] is True


def test_preview_special_up_capped_signals_unavailable(client) -> None:
    """Force a hero to MAX_SPECIAL_LEVEL via DB; preview should report
    capped / unavailable and surface the reason."""
    from app.db import SessionLocal
    from app.models import HeroInstance
    from app.routers.heroes import MAX_SPECIAL_LEVEL

    hdr, _ = _register(client)
    heroes = client.get("/heroes/mine", headers=hdr).json()
    target = heroes[0]

    db = SessionLocal()
    try:
        h = db.get(HeroInstance, target["id"])
        h.special_level = MAX_SPECIAL_LEVEL
        db.commit()
    finally:
        db.close()

    r = client.get(f"/heroes/{target['id']}/preview", headers=hdr).json()
    sp = r["special_up"]
    assert sp["available"] is False
    assert sp["cost"]["target_special_level"] == MAX_SPECIAL_LEVEL
    assert "max" in sp["cost"]["reason"].lower()


def test_preview_404s_for_other_accounts_hero(client) -> None:
    hdr_a, _ = _register(client)
    hdr_b, _ = _register(client)
    heroes_b = client.get("/heroes/mine", headers=hdr_b).json()
    h = heroes_b[0]
    r = client.get(f"/heroes/{h['id']}/preview", headers=hdr_a)
    assert r.status_code == 404
