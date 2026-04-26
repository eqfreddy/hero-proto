"""Phase 2.2 — Myth-tier event banner summon.

Verifies the Mother's Day acceptance criterion: "Myth-tier event hero
is summonable during active event window only, verified in a test."

Tests:
- No active EVENT_BANNER → /summon/event-banner returns 409.
- Active banner → pull grants the configured Myth hero.
- Per-account cap enforced.
- Shard cost charged.
- Status endpoint reports remaining pulls.
- Banner with bad hero_template_code 500s gracefully.
"""

from __future__ import annotations

import random
from datetime import timedelta


def _register(client) -> tuple[dict, int]:
    email = f"mythbanner+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _set_shards(aid: int, n: int) -> None:
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.shards = n
        db.commit()
    finally:
        db.close()


def _activate_banner(
    name: str = "TestBanner",
    hero_code: str = "applecrumb",
    shard_cost: int = 5,
    cap: int = 3,
):
    """Insert + return an active EVENT_BANNER LiveOpsEvent. Cleans up
    earlier rows of the same name so reruns are idempotent."""
    import json
    from app.db import SessionLocal
    from app.liveops import utcnow
    from app.models import LiveOpsEvent, LiveOpsKind

    db = SessionLocal()
    try:
        for stale in db.query(LiveOpsEvent).filter_by(name=name).all():
            db.delete(stale)
        db.commit()
        now = utcnow()
        ev = LiveOpsEvent(
            kind=LiveOpsKind.EVENT_BANNER,
            name=name,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=24),
            payload_json=json.dumps({
                "hero_template_code": hero_code,
                "shard_cost": shard_cost,
                "per_account_cap": cap,
            }),
        )
        db.add(ev)
        db.commit()
        return ev.id
    finally:
        db.close()


def _delete_event(banner_id: int) -> None:
    from app.db import SessionLocal
    from app.models import LiveOpsEvent
    db = SessionLocal()
    try:
        ev = db.get(LiveOpsEvent, banner_id)
        if ev is not None:
            db.delete(ev)
            db.commit()
    finally:
        db.close()


# --- Tests -----------------------------------------------------------------


def test_no_active_banner_returns_409(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/summon/event-banner", headers=hdr)
    assert r.status_code == 409
    assert "no event banner" in r.text.lower()


def test_status_endpoint_reports_inactive_when_no_banner(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/summon/event-banner", headers=hdr)
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_active_banner_grants_configured_hero(client) -> None:
    hdr, aid = _register(client)
    _set_shards(aid, 50)
    bid = _activate_banner(hero_code="applecrumb", shard_cost=8, cap=3)
    try:
        # Status reflects active banner.
        status = client.get("/summon/event-banner", headers=hdr).json()
        assert status["active"] is True
        assert status["hero_template_code"] == "applecrumb"
        assert status["pulls_used"] == 0
        assert status["pulls_remaining"] == 3

        before = client.get("/me", headers=hdr).json()["shards"]
        r = client.post("/summon/event-banner", headers=hdr)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["rarity"] == "MYTH"
        # Shards charged exactly the configured amount.
        after = client.get("/me", headers=hdr).json()["shards"]
        assert after == before - 8, (before, after)

        # Status updated.
        status2 = client.get("/summon/event-banner", headers=hdr).json()
        assert status2["pulls_used"] == 1
        assert status2["pulls_remaining"] == 2
    finally:
        _delete_event(bid)


def test_per_account_cap_enforced(client) -> None:
    hdr, aid = _register(client)
    _set_shards(aid, 1000)
    bid = _activate_banner(hero_code="applecrumb", shard_cost=1, cap=2)
    try:
        for _ in range(2):
            r = client.post("/summon/event-banner", headers=hdr)
            assert r.status_code == 201
        r = client.post("/summon/event-banner", headers=hdr)
        assert r.status_code == 409
        assert "cap reached" in r.text.lower()
    finally:
        _delete_event(bid)


def test_insufficient_shards_returns_409(client) -> None:
    hdr, aid = _register(client)
    _set_shards(aid, 0)
    bid = _activate_banner(hero_code="applecrumb", shard_cost=8, cap=3)
    try:
        r = client.post("/summon/event-banner", headers=hdr)
        assert r.status_code == 409
        assert "shards" in r.text.lower()
    finally:
        _delete_event(bid)


def test_misconfigured_banner_500s(client) -> None:
    """A banner pointing at a hero template that doesn't exist should
    fail loudly so ops sees the typo immediately."""
    hdr, aid = _register(client)
    _set_shards(aid, 50)
    bid = _activate_banner(hero_code="nonexistent_hero", shard_cost=1, cap=3)
    try:
        r = client.post("/summon/event-banner", headers=hdr)
        assert r.status_code == 500
        assert "not seeded" in r.text.lower()
    finally:
        _delete_event(bid)


def test_pull_after_banner_window_expires_returns_409(client) -> None:
    """Force the banner ends_at into the past — endpoint must treat as
    no-active-banner."""
    from app.db import SessionLocal
    from app.liveops import utcnow
    from app.models import LiveOpsEvent

    hdr, aid = _register(client)
    _set_shards(aid, 50)
    bid = _activate_banner(hero_code="applecrumb", shard_cost=1, cap=3)
    try:
        db = SessionLocal()
        try:
            ev = db.get(LiveOpsEvent, bid)
            ev.ends_at = utcnow() - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()
        r = client.post("/summon/event-banner", headers=hdr)
        assert r.status_code == 409
    finally:
        _delete_event(bid)
