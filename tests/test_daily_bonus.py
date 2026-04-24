"""Daily login bonus: streak math, reward grants, cooldown gate, reset-after-48h."""

from __future__ import annotations

import random
from datetime import timedelta

from app.db import SessionLocal
from app.models import Account, utcnow


def _register(client, prefix: str = "dbn") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _set_last_claim(account_id: int, ts) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.last_daily_claim_at = ts
        db.commit()


def _set_streak(account_id: int, streak: int, last_claim_hours_ago: float | None = None) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.daily_streak = streak
        if last_claim_hours_ago is not None:
            a.last_daily_claim_at = utcnow() - timedelta(hours=last_claim_hours_ago)
        db.commit()


def test_status_shows_day_one_for_new_account(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/me/daily-bonus", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["current_streak"] == 0
    assert body["next_streak_if_claimed"] == 1
    assert body["can_claim"] is True
    # Day-1 reward is 200 coins per the table.
    assert body["today_reward"]["coins"] == 200


def test_first_claim_grants_day_one_reward_and_sets_streak(client) -> None:
    hdr, account_id = _register(client)
    before = client.get("/me", headers=hdr).json()
    r = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["streak_after"] == 1
    assert body["granted"]["coins"] == 200
    assert body["was_reset"] is False

    after = client.get("/me", headers=hdr).json()
    assert after["coins"] == before["coins"] + 200


def test_second_claim_same_day_is_rejected(client) -> None:
    hdr, _ = _register(client)
    r1 = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r1.status_code == 201
    r2 = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r2.status_code == 409
    assert "not yet available" in r2.text.lower()


def test_claim_next_day_advances_streak(client) -> None:
    hdr, account_id = _register(client)
    client.post("/me/daily-bonus/claim", headers=hdr)
    # Nudge last_claim 22 hours into the past — past the cooldown (20h) but within 48h.
    _set_streak(account_id, streak=1, last_claim_hours_ago=22)

    r = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["streak_after"] == 2
    # Day 2 reward in the table: 300 coins + 2 shards.
    assert body["granted"]["coins"] == 300
    assert body["granted"]["shards"] == 2
    assert body["was_reset"] is False


def test_missed_day_resets_streak(client) -> None:
    hdr, account_id = _register(client)
    client.post("/me/daily-bonus/claim", headers=hdr)
    # Three days ago — beyond the 48h reset window.
    _set_streak(account_id, streak=3, last_claim_hours_ago=72)

    r = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r.status_code == 201
    body = r.json()
    assert body["streak_after"] == 1, "streak should reset to 1 after 48h gap"
    assert body["was_reset"] is True
    assert body["granted"]["coins"] == 200  # back to day-1 reward


def test_day_seven_grants_premium_reward(client) -> None:
    hdr, account_id = _register(client)
    # Seed a 6-day streak with last claim 22h ago so claim advances to day 7.
    _set_streak(account_id, streak=6, last_claim_hours_ago=22)
    before = client.get("/me", headers=hdr).json()

    r = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r.status_code == 201
    body = r.json()
    assert body["streak_after"] == 7
    # Day 7 grants 200 gems + 3 access cards.
    assert body["granted"]["gems"] == 200
    assert body["granted"]["access_cards"] == 3

    after = client.get("/me", headers=hdr).json()
    assert after["gems"] == before["gems"] + 200
    assert after["access_cards"] == before["access_cards"] + 3


def test_day_eight_wraps_to_day_one_reward(client) -> None:
    """After day 7, cycle wraps: day 8 = day 1 reward (coins only)."""
    hdr, account_id = _register(client)
    _set_streak(account_id, streak=7, last_claim_hours_ago=22)

    r = client.post("/me/daily-bonus/claim", headers=hdr)
    assert r.status_code == 201
    body = r.json()
    assert body["streak_after"] == 8
    # Wrap to day-1 reward.
    assert body["granted"]["coins"] == 200
    assert body["granted"]["gems"] == 0


def test_htmx_me_partial_shows_claim_card(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/app/partials/me", headers=hdr)
    assert r.status_code == 200
    assert "Daily Login Bonus" in r.text
    assert "Claim" in r.text


def test_htmx_me_partial_shows_cooldown_after_claim(client) -> None:
    hdr, _ = _register(client)
    client.post("/me/daily-bonus/claim", headers=hdr)
    r = client.get("/app/partials/me", headers=hdr)
    assert r.status_code == 200
    assert "Current streak:" in r.text
    # Button should be disabled / show claimed state.
    assert "Claimed ✓" in r.text


def test_status_cooldown_window_correct(client) -> None:
    hdr, account_id = _register(client)
    # Last claimed 5 hours ago — well inside the 20h cooldown.
    _set_streak(account_id, streak=1, last_claim_hours_ago=5)
    r = client.get("/me/daily-bonus", headers=hdr)
    body = r.json()
    assert body["can_claim"] is False
    assert body["next_claim_at"] is not None
