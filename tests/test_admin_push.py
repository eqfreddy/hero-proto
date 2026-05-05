"""Phase 4.3 — admin push diagnostics endpoints."""
from __future__ import annotations

import random

from app.db import SessionLocal
from app.models import Account, AdminAuditLog, DeviceToken
from sqlalchemy import select


def _register(client, prefix: str = "pushadm") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _make_admin(account_id: int) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.is_admin = True
        db.commit()


def test_push_status_requires_admin(client) -> None:
    hdr, _ = _register(client, "plain")
    r = client.get("/admin/push/status", headers=hdr)
    assert r.status_code == 403


def test_push_status_reports_unconfigured(client) -> None:
    """No FCM/APNs env vars set in test → both providers report False."""
    hdr, admin_id = _register(client, "pushadm")
    _make_admin(admin_id)

    r = client.get("/admin/push/status", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert "fcm" in body and "apns" in body
    # Test env should not have real creds wired up.
    assert body["fcm"] is False
    assert body["apns"] is False


def test_push_test_returns_zero_when_no_devices(client) -> None:
    hdr, admin_id = _register(client, "pushadm")
    _make_admin(admin_id)

    r = client.post(
        "/admin/push/test",
        headers=hdr,
        json={"title": "hi", "body": "test"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sent"] == 0  # no creds + no devices


def test_push_test_no_op_when_unconfigured_even_with_devices(client) -> None:
    """Devices registered but no creds → still returns sent=0, no errors."""
    hdr, admin_id = _register(client, "pushadm")
    _make_admin(admin_id)

    r = client.post(
        "/notifications/device-token",
        headers=hdr,
        json={"token": "fake-fcm-token", "platform": "fcm"},
    )
    assert r.status_code == 204

    r = client.post(
        "/admin/push/test",
        headers=hdr,
        json={"title": "hi", "body": "test"},
    )
    assert r.status_code == 200
    # send_push_to_account short-circuits when no providers configured.
    assert r.json()["sent"] == 0

    # Token should still be in the DB (no stale-prune happened).
    with SessionLocal() as db:
        rows = db.scalars(select(DeviceToken).where(DeviceToken.account_id == admin_id)).all()
        assert len(rows) == 1


def test_push_test_writes_audit_log(client) -> None:
    hdr, admin_id = _register(client, "pushadm")
    _make_admin(admin_id)

    r = client.post(
        "/admin/push/test",
        headers=hdr,
        json={"title": "diag", "body": ""},
    )
    assert r.status_code == 200

    with SessionLocal() as db:
        rows = db.scalars(
            select(AdminAuditLog).where(AdminAuditLog.actor_id == admin_id)
        ).all()
        assert any(r.action == "push_test" for r in rows)


def test_push_test_requires_admin(client) -> None:
    hdr, _ = _register(client, "plain")
    r = client.post(
        "/admin/push/test",
        headers=hdr,
        json={"title": "x", "body": "y"},
    )
    assert r.status_code == 403
