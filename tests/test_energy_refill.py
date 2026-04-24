"""Gem-for-energy refill + daily cap + SPEND_GEMS quest progress hook."""

from __future__ import annotations

import random

from app.daily import day_key
from app.db import SessionLocal
from app.models import Account, DailyQuest, DailyQuestKind, DailyQuestStatus


def _register(client, prefix: str = "ref") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _grant_gems_and_drain_energy(account_id: int, gems: int = 500) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.gems = gems
        a.energy_stored = 0
        db.commit()


def test_refill_full_flow(client) -> None:
    hdr, aid = _register(client)
    _grant_gems_and_drain_energy(aid, gems=300)

    r = client.post("/me/energy/refill", headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["gems_spent"] == 50
    assert body["refills_today"] == 1
    assert body["refills_remaining_today"] == 2
    assert body["energy"] > 0

    # /me reflects the new state.
    me = client.get("/me", headers=hdr).json()
    assert me["gems"] == 250
    assert me["energy"] == me["energy_cap"]


def test_refill_requires_gems(client) -> None:
    hdr, aid = _register(client)
    # Zero gems, drained energy.
    _grant_gems_and_drain_energy(aid, gems=0)
    r = client.post("/me/energy/refill", headers=hdr)
    assert r.status_code == 409
    assert "not enough gems" in r.text.lower()


def test_refill_rejected_when_full(client) -> None:
    hdr, aid = _register(client)
    # Full energy, plenty of gems.
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.gems = 500
        db.commit()
    r = client.post("/me/energy/refill", headers=hdr)
    assert r.status_code == 409
    assert "cap" in r.text.lower()


def test_daily_refill_cap_enforced(client) -> None:
    hdr, aid = _register(client)
    _grant_gems_and_drain_energy(aid, gems=500)

    # Three refills allowed.
    for i in range(3):
        _grant_gems_and_drain_energy(aid, gems=500)  # keep gems/energy valid each cycle
        # Re-seed refills_today_count for this day via DB? Actually we want to preserve it.
        # Just drain energy and top up gems — counter stays.
        with SessionLocal() as db:
            a = db.get(Account, aid)
            a.gems = 500
            a.energy_stored = 0
            db.commit()
        r = client.post("/me/energy/refill", headers=hdr)
        assert r.status_code == 201, f"refill #{i+1} failed: {r.text}"

    # Fourth refill today is rejected.
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.gems = 500
        a.energy_stored = 0
        db.commit()
    r = client.post("/me/energy/refill", headers=hdr)
    assert r.status_code == 409
    assert "daily refill limit" in r.text.lower()


def test_refill_counter_resets_on_new_day(client) -> None:
    hdr, aid = _register(client)
    # Simulate the account having already refilled 3 times on a PRIOR day.
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.gems = 500
        a.energy_stored = 0
        a.refills_today_key = "1970-01-01"  # ancient day key
        a.refills_today_count = 3
        db.commit()

    r = client.post("/me/energy/refill", headers=hdr)
    assert r.status_code == 201, r.text
    # New day — counter reset to 1 (this refill), not 4.
    assert r.json()["refills_today"] == 1


def test_refill_advances_spend_gems_daily_quest(client) -> None:
    """Seed a SPEND_GEMS quest with goal 50; one refill should complete it."""
    hdr, aid = _register(client)
    _grant_gems_and_drain_energy(aid, gems=500)

    with SessionLocal() as db:
        q = DailyQuest(
            account_id=aid,
            day_key=day_key(),
            kind=DailyQuestKind.SPEND_GEMS,
            goal=50,
            progress=0,
            status=DailyQuestStatus.ACTIVE,
            reward_coins=300,
        )
        db.add(q)
        db.commit()
        qid = q.id

    r = client.post("/me/energy/refill", headers=hdr)
    assert r.status_code == 201

    with SessionLocal() as db:
        q = db.get(DailyQuest, qid)
        assert q.progress == 50
        assert q.status == DailyQuestStatus.COMPLETE


def test_refill_button_shows_only_when_below_cap(client) -> None:
    """HTMX /me partial shows refill button only when energy < cap."""
    hdr, aid = _register(client)
    # Full energy: no refill button.
    r = client.get("/app/partials/me", headers=hdr)
    assert r.status_code == 200
    assert 'onclick="refillEnergy(' not in r.text

    # Drain energy: refill button appears.
    _grant_gems_and_drain_energy(aid, gems=500)
    r = client.get("/app/partials/me", headers=hdr)
    assert r.status_code == 200
    assert 'onclick="refillEnergy(' in r.text
    assert "Refill (50💎)" in r.text
