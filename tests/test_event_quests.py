"""Event currency + quests + milestone exchange — end-to-end coverage.

Builds a temporary event spec, monkeypatches active_event_spec to return
it (so tests don't depend on real-world dates), runs activities, claims
quests, redeems milestones. Catches schema/router/state regressions.
"""

from __future__ import annotations

import json
import random
from datetime import timedelta

import pytest

from app import event_state
from app.db import SessionLocal
from app.event_state import EventSpec
from app.models import Account, LiveOpsEvent, LiveOpsKind, utcnow


def _make_test_spec() -> EventSpec:
    """Bare-bones spec used by every test in this module."""
    now = utcnow()
    return EventSpec(
        id="test_event_2026",
        display_name="Test Event",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=24),
        currency_name="Sparks",
        currency_emoji="⚡",
        drops={"battle_win": 5, "summon_pull": 2, "arena_attack": 8, "raid_attack": 12},
        quests=[
            {"code": "win_3", "title": "Win 3 battles", "kind": "WIN_BATTLES", "goal": 3, "currency_reward": 50},
            {"code": "summon_5", "title": "Pull 5 heroes", "kind": "SUMMON_PULLS", "goal": 5, "currency_reward": 30},
        ],
        milestones=[
            {"title": "Cheap pack", "cost": 25, "contents": {"gems": 100}},
            {"title": "Big pack", "cost": 200, "contents": {"gems": 1000, "shards": 50}},
        ],
    )


@pytest.fixture
def active_test_event(monkeypatch):
    """Pin a test spec as the active event + insert a matching LiveOpsEvent
    row so on_activity hooks don't bail on the live-row check.

    Patches every module that imports `active_event_spec` at top level — the
    function name is rebound locally on each `from app.event_state import …`
    so monkeypatching event_state alone misses the consumers.
    """
    spec = _make_test_spec()
    fake = lambda now=None: spec
    monkeypatch.setattr(event_state, "active_event_spec", fake)
    from app.routers import events as _events_router
    monkeypatch.setattr(_events_router, "active_event_spec", fake)
    with SessionLocal() as db:
        live = LiveOpsEvent(
            kind=LiveOpsKind.DOUBLE_REWARDS,
            name="test_event_live_row",
            starts_at=spec.starts_at,
            ends_at=spec.ends_at,
            payload_json=json.dumps({"multiplier": 2.0}),
        )
        db.add(live)
        db.commit()
        live_id = live.id
    yield spec
    # Cleanup the LiveOpsEvent row + every account's event_state for this id.
    with SessionLocal() as db:
        row = db.get(LiveOpsEvent, live_id)
        if row is not None:
            db.delete(row)
        for acct in db.query(Account).all():
            try:
                state = json.loads(acct.event_state_json or "{}")
            except json.JSONDecodeError:
                continue
            if spec.id in state:
                state.pop(spec.id, None)
                acct.event_state_json = json.dumps(state)
        db.commit()


def _register(client) -> tuple[dict, int]:
    email = f"event+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return hdr, client.get("/me", headers=hdr).json()["id"]


def test_no_active_event_returns_404(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/events/active", headers=hdr)
    assert r.status_code == 404


def test_active_event_payload_shape(client, active_test_event) -> None:
    hdr, _ = _register(client)
    r = client.get("/events/active", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "test_event_2026"
    assert body["currency_name"] == "Sparks"
    assert body["currency_balance"] == 0
    assert len(body["quests"]) == 2
    assert len(body["milestones"]) == 2
    assert body["quests"][0]["claimed"] is False


def test_battle_win_drops_currency_and_advances_quest(client, active_test_event) -> None:
    hdr, _ = _register(client)
    # Find tutorial stage for a guaranteed-win battle.
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    roster = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(roster, key=lambda h: h["power"], reverse=True)[:3]]

    won = False
    for _ in range(3):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        assert r.status_code == 201
        if r.json()["outcome"] == "WIN":
            won = True
            break
    assert won

    body = client.get("/events/active", headers=hdr).json()
    # Each battle_win drops 5 ⚡; one win → 5.
    assert body["currency_balance"] >= 5
    win_quest = next(q for q in body["quests"] if q["code"] == "win_3")
    assert win_quest["progress"] >= 1


def test_quest_claim_grants_currency(client, active_test_event) -> None:
    hdr, _ = _register(client)
    # Force-set quest progress directly via state helpers.
    with SessionLocal() as db:
        acct = db.query(Account).filter(Account.email.startswith("event+")).order_by(Account.id.desc()).first()
        from app.event_state import advance_quest
        advance_quest(acct, "test_event_2026", "win_3", amount=3)
        db.commit()

    # Claim — should grant +50 sparks.
    r = client.post("/events/quests/win_3/claim", headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["currency_granted"] == 50
    assert body["currency_balance"] >= 50

    # Second claim 409s.
    r = client.post("/events/quests/win_3/claim", headers=hdr)
    assert r.status_code == 409


def test_claim_incomplete_quest_409(client, active_test_event) -> None:
    hdr, _ = _register(client)
    r = client.post("/events/quests/win_3/claim", headers=hdr)
    assert r.status_code == 409
    assert "not complete" in r.json()["detail"].lower()


def test_claim_unknown_quest_404(client, active_test_event) -> None:
    hdr, _ = _register(client)
    r = client.post("/events/quests/does_not_exist/claim", headers=hdr)
    assert r.status_code == 404


def test_milestone_redeem_spends_currency_and_grants_contents(client, active_test_event) -> None:
    hdr, _ = _register(client)
    with SessionLocal() as db:
        acct = db.query(Account).filter(Account.email.startswith("event+")).order_by(Account.id.desc()).first()
        from app.event_state import grant_currency
        grant_currency(acct, "test_event_2026", 250)
        gems_before = acct.gems
        db.commit()

    # Redeem the cheap pack (25 sparks → 100 gems).
    r = client.post("/events/milestones/0/redeem", headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["spent"] == 25
    assert body["currency_balance"] == 225
    assert body["granted"]["gems"] == 100

    me = client.get("/me", headers=hdr).json()
    assert me["gems"] == gems_before + 100

    # Re-redeem same milestone — 409 idempotent.
    r = client.post("/events/milestones/0/redeem", headers=hdr)
    assert r.status_code == 409


def test_milestone_redeem_insufficient_currency_409(client, active_test_event) -> None:
    hdr, _ = _register(client)
    # Fresh account has 0 sparks, big pack costs 200.
    r = client.post("/events/milestones/1/redeem", headers=hdr)
    assert r.status_code == 409
    assert "not enough" in r.json()["detail"].lower()


def test_milestone_redeem_bad_index_404(client, active_test_event) -> None:
    hdr, _ = _register(client)
    r = client.post("/events/milestones/999/redeem", headers=hdr)
    assert r.status_code == 404


def test_full_round_trip(client, active_test_event) -> None:
    """Battle → quest progress → claim → redeem milestone with that currency."""
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    roster = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(roster, key=lambda h: h["power"], reverse=True)[:3]]

    # Win 5 tutorials to comfortably exceed the win_3 quest goal.
    wins = 0
    for _ in range(15):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        if r.status_code != 201:
            break
        if r.json()["outcome"] == "WIN":
            wins += 1
            if wins >= 5:
                break
    assert wins >= 3, f"need >=3 wins, got {wins}"

    # Quest is complete, claim it for +50 sparks.
    r = client.post("/events/quests/win_3/claim", headers=hdr)
    assert r.status_code == 201
    bal_after_claim = r.json()["currency_balance"]
    # 5 wins × 5 drops = 25 sparks earned, +50 quest reward = 75 minimum
    # (not exact since extra battles past 3rd still drop sparks).
    assert bal_after_claim >= 50

    # Redeem the cheap pack with the haul.
    r = client.post("/events/milestones/0/redeem", headers=hdr)
    assert r.status_code == 201
    assert r.json()["spent"] == 25
