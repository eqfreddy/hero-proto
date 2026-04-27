"""Admin announcements / MOTD: CRUD + public /active + /me banner surfacing."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, AdminAnnouncement


def _register(client, prefix: str = "ann") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _promote(account_id: int) -> None:
    with SessionLocal() as db:
        db.get(Account, account_id).is_admin = True
        db.commit()


def test_non_admin_cannot_create_or_list(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/admin/announcements", json={"title": "x", "body": "y"}, headers=hdr)
    assert r.status_code == 403
    r = client.get("/admin/announcements", headers=hdr)
    assert r.status_code == 403


def test_admin_can_create_and_public_sees_active(client) -> None:
    hdr, admin_id = _register(client, "annadm")
    _promote(admin_id)
    r = client.post(
        "/admin/announcements",
        headers=hdr,
        json={"title": "Maintenance Thursday", "body": "Server down 8-9pm UTC", "priority": 50},
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["title"] == "Maintenance Thursday"
    assert created["is_active"] is True
    assert created["created_by"] == admin_id

    # Public endpoint shows it — no auth required.
    r = client.get("/announcements/active")
    assert r.status_code == 200
    bodies = [a["title"] for a in r.json()]
    assert "Maintenance Thursday" in bodies


def test_active_filters_inactive(client) -> None:
    hdr, admin_id = _register(client, "annoff")
    _promote(admin_id)
    r = client.post(
        "/admin/announcements",
        headers=hdr,
        json={"title": "expired_banner", "body": "old news"},
    )
    aid = r.json()["id"]
    # Turn off.
    client.patch(f"/admin/announcements/{aid}", headers=hdr, json={"is_active": False})
    active = client.get("/announcements/active").json()
    assert not any(a["id"] == aid for a in active)


def test_ends_at_auto_filters_expired(client) -> None:
    hdr, admin_id = _register(client, "annexp")
    _promote(admin_id)
    # Create with past ends_at.
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    r = client.post(
        "/admin/announcements",
        headers=hdr,
        json={"title": "already expired", "body": "gone", "duration_hours": 0.01},
    )
    aid = r.json()["id"]
    # Overwrite ends_at to the past to simulate expired window.
    with SessionLocal() as db:
        a = db.get(AdminAnnouncement, aid)
        a.ends_at = past.replace(tzinfo=None)
        db.commit()
    active = client.get("/announcements/active").json()
    assert not any(a["id"] == aid for a in active)


def test_priority_sorts_highest_first(client) -> None:
    hdr, admin_id = _register(client, "annprio")
    _promote(admin_id)
    client.post("/admin/announcements", headers=hdr, json={"title": "low", "body": "x", "priority": 0})
    client.post("/admin/announcements", headers=hdr, json={"title": "high", "body": "y", "priority": 75})
    client.post("/admin/announcements", headers=hdr, json={"title": "mid", "body": "z", "priority": 30})
    titles = [a["title"] for a in client.get("/announcements/active").json()]
    # "high" then "mid" then "low" — or with other prior test data sprinkled, but high must be before mid/low.
    assert titles.index("high") < titles.index("mid") < titles.index("low")


def test_admin_can_delete(client) -> None:
    hdr, admin_id = _register(client, "anndel")
    _promote(admin_id)
    r = client.post("/admin/announcements", headers=hdr, json={"title": "t", "body": "b"})
    aid = r.json()["id"]
    r = client.delete(f"/admin/announcements/{aid}", headers=hdr)
    assert r.status_code == 200
    assert r.json()["deleted_id"] == aid
    # Gone from public feed.
    active = client.get("/announcements/active").json()
    assert not any(a["id"] == aid for a in active)


def test_ends_at_in_future_still_visible(client) -> None:
    hdr, admin_id = _register(client, "annfut")
    _promote(admin_id)
    r = client.post(
        "/admin/announcements", headers=hdr,
        json={"title": "short window", "body": "2h", "duration_hours": 2},
    )
    assert r.json()["ends_at"] is not None
    active = client.get("/announcements/active").json()
    assert any(a["title"] == "short window" for a in active)
