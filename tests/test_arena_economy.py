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
