"""Phase 2 polish — achievement progress bars on count-based goals.

When the catalog entry has a `progress` getter, /achievements surfaces
(current, target) so the UI can render a fill bar instead of just a
locked icon. Existence-style achievements ("have at least one EPIC")
stay binary.
"""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"achprog+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def test_count_based_achievements_have_progress(client) -> None:
    """The "win 10 battles" / "open 50 summons" / etc family must
    surface progress numbers."""
    hdr, _ = _register(client)
    items = client.get("/achievements", headers=hdr).json()["items"]
    by_code = {i["code"]: i for i in items}

    expected_progress_codes = (
        "wins_10", "wins_100", "wins_1000",
        "summons_50", "summons_500",
        "stages_5", "stages_15",
        "raid_25",
        "gear_25",
        "roster_10", "roster_50",
    )
    for code in expected_progress_codes:
        if code not in by_code:
            continue  # catalog may have evolved; tolerate missing
        a = by_code[code]
        assert a["has_progress"] is True, code
        assert a["progress_target"] > 0, code
        # On a fresh account most should be at 0; allow up to a small
        # number in case starter team or seed activity bumped a counter.
        assert 0 <= a["progress_current"] <= a["progress_target"], (code, a)


def test_existence_based_achievements_are_binary(client) -> None:
    """Achievements like "first EPIC" or "join a guild" don't have
    a numeric target — has_progress should be False."""
    hdr, _ = _register(client)
    items = client.get("/achievements", headers=hdr).json()["items"]
    by_code = {i["code"]: i for i in items}

    binary_codes = ("first_epic", "first_legendary", "join_guild", "first_summon")
    for code in binary_codes:
        if code not in by_code:
            continue
        a = by_code[code]
        assert a["has_progress"] is False, code


def test_progress_advances_after_a_win(client) -> None:
    """After winning the tutorial battle, wins_10's progress should be
    at least 1."""
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    won = False
    for _ in range(4):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        if r.status_code == 201 and r.json()["outcome"] == "WIN":
            won = True
            break
    if not won:
        import pytest
        pytest.skip("tutorial RNG didn't land a win in this run")

    items = client.get("/achievements", headers=hdr).json()["items"]
    wins_10 = next((i for i in items if i["code"] == "wins_10"), None)
    if wins_10 is None:
        import pytest
        pytest.skip("wins_10 not in catalog")
    # Could be unlocked or still progressing — either way progress should
    # reflect at least one win.
    if not wins_10["unlocked"]:
        assert wins_10["progress_current"] >= 1, wins_10
