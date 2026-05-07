"""Arena ticket regen helpers — pure-function tests."""
from __future__ import annotations

from datetime import timedelta

from app.config import settings
from app.economy import (
    compute_arena_tickets,
    consume_arena_ticket,
    seconds_until_next_energy,
    seconds_until_next_ticket,
)
from app.models import Account, utcnow


def _account(stored: int = 0, seconds_ago: int = 0) -> Account:
    a = Account(
        email="t@t",
        password_hash="x",
        coins=0,
        gems=0,
        shards=0,
        arena_tickets_stored=stored,
        arena_tickets_last_tick_at=utcnow() - timedelta(seconds=seconds_ago),
    )
    return a


def test_compute_arena_tickets_below_cap_ticks_correctly():
    a = _account(stored=0, seconds_ago=settings.arena_tickets_regen_seconds * 2)
    assert compute_arena_tickets(a) == 2


def test_compute_arena_tickets_caps_at_max():
    a = _account(stored=3, seconds_ago=settings.arena_tickets_regen_seconds * 99)
    assert compute_arena_tickets(a) == settings.arena_tickets_cap


def test_compute_arena_tickets_at_cap_returns_cap_unchanged():
    a = _account(stored=settings.arena_tickets_cap, seconds_ago=10)
    assert compute_arena_tickets(a) == settings.arena_tickets_cap


def test_consume_arena_ticket_returns_false_at_zero():
    a = _account(stored=0, seconds_ago=0)
    assert consume_arena_ticket(a) is False
    assert a.arena_tickets_stored == 0


def test_consume_arena_ticket_decrements_on_success():
    a = _account(stored=3, seconds_ago=0)
    assert consume_arena_ticket(a) is True
    assert a.arena_tickets_stored == 2


def test_consume_arena_ticket_flushes_regen_first():
    # 1 stored, regen produces 2 more → consume → 2 left.
    a = _account(stored=1, seconds_ago=settings.arena_tickets_regen_seconds * 2)
    assert consume_arena_ticket(a) is True
    assert a.arena_tickets_stored == 2


def test_seconds_until_next_ticket_at_cap_is_zero():
    a = _account(stored=settings.arena_tickets_cap, seconds_ago=0)
    assert seconds_until_next_ticket(a) == 0


def test_seconds_until_next_ticket_below_cap():
    # Just ticked, so the full regen interval remains.
    a = _account(stored=0, seconds_ago=0)
    assert seconds_until_next_ticket(a) == settings.arena_tickets_regen_seconds


def test_seconds_until_next_ticket_partial():
    a = _account(stored=0, seconds_ago=settings.arena_tickets_regen_seconds // 4)
    expected = settings.arena_tickets_regen_seconds - settings.arena_tickets_regen_seconds // 4
    # Allow ±2 seconds of clock slop.
    assert abs(seconds_until_next_ticket(a) - expected) <= 2


def test_seconds_until_next_energy_at_cap_is_zero():
    a = Account(
        email="e@e", password_hash="x", coins=0, gems=0, shards=0,
        energy_stored=settings.energy_cap,
        energy_last_tick_at=utcnow(),
    )
    assert seconds_until_next_energy(a) == 0


# ---------------------------------------------------------------------------
# Integration tests — ticket gate + drip rewards on /arena/attack
# ---------------------------------------------------------------------------


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_attacker_and_defender(client, prefix):
    """Returns (atk_hdr, def_id, atk_team)."""
    import random
    def_email = f"{prefix}-def-{random.randint(100000, 999999)}@example.com"
    def_hdr = _register(client, def_email)
    client.post("/summon/x10", headers=def_hdr)
    def_roster = sorted(
        client.get("/heroes/mine", headers=def_hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    def_team = [h["id"] for h in def_roster[:3]]
    def_id = client.get("/me", headers=def_hdr).json()["id"]
    client.put("/arena/defense", json={"team": def_team}, headers=def_hdr)

    atk_email = f"{prefix}-atk-{random.randint(100000, 999999)}@example.com"
    atk_hdr = _register(client, atk_email)
    client.post("/summon/x10", headers=atk_hdr)
    atk_roster = sorted(
        client.get("/heroes/mine", headers=atk_hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    atk_team = [h["id"] for h in atk_roster[:3]]
    return atk_hdr, def_id, atk_team


def test_arena_attack_returns_429_when_no_tickets(client):
    from app.db import SessionLocal
    from app.models import Account
    atk_hdr, def_id, atk_team = _setup_attacker_and_defender(client, "tix")
    me = client.get("/me", headers=atk_hdr).json()

    # Drain tickets directly via DB.
    db = SessionLocal()
    try:
        a = db.get(Account, me["id"])
        a.arena_tickets_stored = 0
        a.arena_tickets_last_tick_at = utcnow()
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 429, r.text
    assert "Retry-After" in r.headers


def test_arena_attack_drips_rewards(client):
    """Attacker receives coins/shards/gems based on outcome."""
    atk_hdr, def_id, atk_team = _setup_attacker_and_defender(client, "drip")
    me_before = client.get("/me", headers=atk_hdr).json()

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201
    match = r.json()
    assert "rewards" in match
    assert match["rewards"]["coins"] >= 20  # loss=25 ±20%, win=75 ±20% — both above 20

    me_after = client.get("/me", headers=atk_hdr).json()
    assert me_after["coins"] >= me_before["coins"] + match["rewards"]["coins"]
    assert me_after["shards"] >= me_before["shards"] + match["rewards"]["shards"]
    assert me_after["gems"] >= me_before["gems"] + match["rewards"]["gems"]


def test_arena_attack_decrements_tickets(client):
    atk_hdr, def_id, atk_team = _setup_attacker_and_defender(client, "decr")
    before = client.get("/me", headers=atk_hdr).json()["arena_tickets"]

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201

    after = client.get("/me", headers=atk_hdr).json()["arena_tickets"]
    assert after == before - 1
