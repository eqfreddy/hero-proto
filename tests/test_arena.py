"""Arena: attack flow, match persistence, replay endpoint, auth gating."""

from __future__ import annotations

import json
import random

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, ArenaMatch, DefenseTeam


def _register_and_team(client, prefix: str) -> tuple[dict[str, str], int, list[int]]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    # Summon 10 so there's a team.
    client.post("/summon/x10", headers=hdr)
    roster = sorted(
        client.get("/heroes/mine", headers=hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    team = [h["id"] for h in roster[:3]]
    return hdr, me["id"], team


def _setup_defender_with_defense_team(client) -> tuple[dict[str, str], int, list[int]]:
    hdr, acct_id, team = _register_and_team(client, "defender")
    # Set defense team via the arena router.
    r = client.put("/arena/defense", json={"team": team}, headers=hdr)
    assert r.status_code == 200, r.text
    return hdr, acct_id, team


def test_arena_attack_stores_participants(client) -> None:
    """Each completed arena match now carries participants_json with both teams."""
    _def_hdr, def_id, _def_team = _setup_defender_with_defense_team(client)
    atk_hdr, atk_id, atk_team = _register_and_team(client, "attacker")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201, r.text
    match = r.json()
    parts = match["participants"]
    # 3 attackers + 3 defenders = 6 participants, all with template_code.
    assert len(parts) == 6, f"expected 6 participants, got {len(parts)}: {parts}"
    assert all(p["template_code"] for p in parts), "every participant needs template_code"
    sides = {p["side"] for p in parts}
    assert sides == {"A", "B"}


def test_get_arena_match_returns_full_payload_to_attacker(client) -> None:
    _def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atk2")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    match_id = r.json()["id"]

    r = client.get(f"/arena/matches/{match_id}", headers=atk_hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == match_id
    assert len(body["participants"]) == 6
    assert len(body["log"]) > 0
    # Log has END event at the tail, per combat.py contract.
    assert any(e.get("type") == "END" for e in body["log"])


def test_get_arena_match_allowed_for_defender_too(client) -> None:
    """Defenders can review matches where they were attacked."""
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atk3")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    match_id = r.json()["id"]

    r = client.get(f"/arena/matches/{match_id}", headers=def_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == match_id


def test_get_arena_match_foreign_returns_404(client) -> None:
    """An uninvolved third party gets 404, not 403 — don't leak existence."""
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atk4")
    other_hdr, _, _ = _register_and_team(client, "rando")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    match_id = r.json()["id"]

    r = client.get(f"/arena/matches/{match_id}", headers=other_hdr)
    assert r.status_code == 404


def test_get_arena_match_requires_auth(client) -> None:
    r = client.get("/arena/matches/1")
    assert r.status_code == 401


def test_get_nonexistent_arena_match_is_404(client) -> None:
    hdr, _, _ = _register_and_team(client, "ghost")
    r = client.get("/arena/matches/9999999", headers=hdr)
    assert r.status_code == 404


def test_opponents_prefer_rating_proximity(client) -> None:
    """Matchmaking should favor defenders within ±200 rating when pool is dense enough."""
    # Seed a handful of defenders at varied ratings: 500, 1000, 1500, 2000, 2500.
    targets = [500, 1000, 1500, 2000, 2500]
    defender_ids = []
    for rating in targets:
        hdr, aid, team = _register_and_team(client, f"rb{rating}")
        client.put("/arena/defense", json={"team": team}, headers=hdr)
        # Patch rating directly — arena win/loss is the only natural way to move
        # the number, and we want precise values.
        with SessionLocal() as db:
            a = db.get(Account, aid)
            a.arena_rating = rating
            db.commit()
        defender_ids.append((aid, rating))

    # Attacker pinned at 1500 — should match the 1500 and 1400 and 1600-ish bucket first.
    atk_hdr, atk_id, _atk_team = _register_and_team(client, "atkmm")
    with SessionLocal() as db:
        a = db.get(Account, atk_id)
        a.arena_rating = 1500
        db.commit()

    r = client.get("/arena/opponents", headers=atk_hdr)
    assert r.status_code == 200
    opps = r.json()
    assert opps, "expected at least one opponent"
    # With 5 defenders at spacing 500, only the 1500 defender is in the ±200 window.
    # Matchmaking widens until it has OPPONENT_SAMPLE_SIZE=3 candidates → next window
    # is ±400, still only 1500. Next ±800 brings in 1000 and 2000. So returned pool
    # should be drawn from {1000, 1500, 2000}, NOT the 500 or 2500 outliers.
    returned_ratings = {o["arena_rating"] for o in opps}
    assert 500 not in returned_ratings, f"pulled a too-low-rated opponent: {returned_ratings}"
    assert 2500 not in returned_ratings, f"pulled a too-high-rated opponent: {returned_ratings}"


def test_opponents_skips_banned_defenders(client) -> None:
    """Banned accounts shouldn't appear in matchmaking even if they have a defense team."""
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    # Ban the defender.
    with SessionLocal() as db:
        a = db.get(Account, def_id)
        a.is_banned = True
        db.commit()

    atk_hdr, _, _ = _register_and_team(client, "atkban")
    r = client.get("/arena/opponents", headers=atk_hdr)
    assert r.status_code == 200
    returned_ids = {o["account_id"] for o in r.json()}
    assert def_id not in returned_ids, "banned defender leaked into opponent list"


def test_opponents_widens_window_when_pool_is_sparse(client) -> None:
    """With an attacker rating way off the grid, matchmaking's None-window fallback
    still returns opponents rather than an empty list."""
    atk_hdr, atk_id, _ = _register_and_team(client, "farfarfar")
    with SessionLocal() as db:
        a = db.get(Account, atk_id)
        a.arena_rating = 9999  # well beyond any seeded defender's rating
        db.commit()

    r = client.get("/arena/opponents", headers=atk_hdr)
    assert r.status_code == 200
    # The widening fallback (None window) should find at least one defender from the
    # shared test DB, even though no one is within ±800 of 9999.
    opps = r.json()
    assert opps, "fallback widening failed — got empty opponent list despite defenders existing"


def test_arena_partial_shows_recent_matches_with_replay_link(client) -> None:
    """After an arena attack, the HTMX partial should list the match with a replay link."""
    _def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, _, atk_team = _register_and_team(client, "atkrepl")

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201
    match_id = r.json()["id"]

    r = client.get("/app/partials/arena", headers=atk_hdr)
    assert r.status_code == 200
    body = r.text
    # Recent matches section + per-row replay link pointing at the Phaser page
    # in arena mode.
    assert "Recent matches" in body
    assert f"/app/battle-replay.html?id={match_id}&amp;mode=arena" in body or \
           f"/app/battle-replay.html?id={match_id}&mode=arena" in body


def test_arena_partial_hides_recent_matches_when_empty(client) -> None:
    """Fresh account with no arena history should not render the Recent matches card."""
    hdr, _, _ = _register_and_team(client, "nohist")
    r = client.get("/app/partials/arena", headers=hdr)
    assert r.status_code == 200
    # Defender/opponents cards always render; Recent matches card only when matches exist.
    assert "Recent matches" not in r.text


def test_arena_partial_attack_uses_correct_field_name(client) -> None:
    """Regression check: the HTMX attack POST must send defender_account_id, not defender_id."""
    hdr, _, _ = _register_and_team(client, "fieldcheck")
    r = client.get("/app/partials/arena", headers=hdr)
    assert r.status_code == 200
    assert "defender_account_id" in r.text, "arena partial JS must POST defender_account_id"
    assert '"defender_id"' not in r.text, "old field name still present — bug regression"


def test_opponents_excludes_recently_attacked(client) -> None:
    """After attacking defender X, /opponents should exclude X until the cooldown elapses."""
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)

    # Spin up a second defender so the pool has somewhere to substitute.
    def_hdr2, def_id2, def_team2 = _register_and_team(client, "rcd2")
    client.put("/arena/defense", json={"team": def_team2}, headers=def_hdr2)

    atk_hdr, _, atk_team = _register_and_team(client, "attrc")

    # Attack the first defender.
    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201

    # Now /opponents should not include def_id (cooldown) as long as another
    # defender is available at any rating window.
    r = client.get("/arena/opponents", headers=atk_hdr)
    assert r.status_code == 200
    returned_ids = {o["account_id"] for o in r.json()}
    assert def_id not in returned_ids, \
        f"just-attacked defender {def_id} should be excluded; got {returned_ids}"


def test_opponents_falls_back_to_recent_if_pool_empty(client) -> None:
    """When the only available defender is in the cooldown set, fall back
    and show them anyway — better than returning no opponents."""
    from datetime import timedelta
    from app.db import SessionLocal
    from app.models import Account as _Acct

    # One defender only.
    def_hdr, def_id, _ = _setup_defender_with_defense_team(client)
    atk_hdr, atk_id, atk_team = _register_and_team(client, "atkfb")

    # Pin both accounts to the same rating so the ±200 window finds the defender.
    with SessionLocal() as db:
        db.get(_Acct, def_id).arena_rating = 1000
        db.get(_Acct, atk_id).arena_rating = 1000
        db.commit()

    # Attack them first, so they're in the recent-attack set.
    client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )

    # Even though def_id is in the recent set, they should surface via the
    # fallback path since the pool (in the shared DB) has many defenders, but
    # specifically at the attacker's rating and not in the recent set there
    # may be none. Either way: the call shouldn't return empty.
    r = client.get("/arena/opponents", headers=atk_hdr)
    assert r.status_code == 200
    # Not asserting def_id IS present (shared DB has other defenders), just
    # that the call returns something.
    assert r.json(), "opponents call should never return empty when any defender exists"


def test_opponents_returns_unique_ids(client) -> None:
    """Sanity: no duplicate account_ids in a single /opponents response."""
    hdr, _, _ = _register_and_team(client, "atkuniq")
    r = client.get("/arena/opponents", headers=hdr)
    assert r.status_code == 200
    ids = [o["account_id"] for o in r.json()]
    assert len(ids) == len(set(ids)), f"duplicate opponent ids: {ids}"
