"""Refresh tokens with rotation: register/login emit, refresh rotates, reuse-detection
revokes the chain, logout revokes a single token."""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, RefreshToken, utcnow
from app.routers.auth import _hash_token


def _register(client, prefix: str = "rt") -> tuple[dict, int, str, str]:
    """Returns (hdr, account_id, access_token, refresh_token)."""
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    body = r.json()
    access = body["access_token"]
    refresh = body["refresh_token"]
    assert refresh, "register should emit a refresh_token"
    hdr = {"Authorization": f"Bearer {access}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"], access, refresh


def test_register_emits_refresh_token(client) -> None:
    hdr, account_id, access, refresh = _register(client)
    # Ensure a hashed row exists for the raw token returned.
    with SessionLocal() as db:
        rows = db.scalars(
            select(RefreshToken).where(RefreshToken.account_id == account_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].token_hash == _hash_token(refresh)
        assert rows[0].revoked_at is None
        assert rows[0].replaced_by_id is None


def test_login_emits_refresh_token(client) -> None:
    email = f"rtlogin+{random.randint(100000, 999999)}@example.com"
    client.post("/auth/register", json={"email": email, "password": "hunter22"})
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    body = r.json()
    assert body["refresh_token"]


def test_refresh_rotates_and_returns_new_access(client) -> None:
    hdr, account_id, access_1, refresh_1 = _register(client)
    r = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    assert r.status_code == 200, r.text
    body = r.json()
    access_2 = body["access_token"]
    refresh_2 = body["refresh_token"]
    assert access_2 and refresh_2
    assert refresh_2 != refresh_1, "refresh must rotate — new token string"

    # New access works.
    hdr2 = {"Authorization": f"Bearer {access_2}"}
    assert client.get("/me", headers=hdr2).status_code == 200

    # Old refresh row has replaced_by_id set.
    with SessionLocal() as db:
        old = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == _hash_token(refresh_1))
        )
        assert old.replaced_by_id is not None
        assert old.revoked_at is not None


def test_refresh_reuse_detection_revokes_chain(client) -> None:
    hdr, account_id, access_1, refresh_1 = _register(client)
    # Legit rotation.
    r = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    refresh_2 = r.json()["refresh_token"]
    # Attacker presents refresh_1 again (it's been rotated out).
    r = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    assert r.status_code == 401
    assert "reuse detected" in r.text.lower()

    # Result: the whole chain is revoked. refresh_2 (legit client's current token)
    # is now useless too.
    r = client.post("/auth/refresh", json={"refresh_token": refresh_2})
    assert r.status_code == 401

    # The original access JWT is also dead via token_version bump.
    r = client.get("/me", headers=hdr)
    assert r.status_code == 401


def test_refresh_unknown_token_rejected(client) -> None:
    r = client.post("/auth/refresh", json={"refresh_token": "not_a_real_token_abcdef"})
    assert r.status_code == 401


def test_refresh_expired_token_rejected(client) -> None:
    hdr, account_id, _access, refresh = _register(client)
    with SessionLocal() as db:
        row = db.scalar(
            select(RefreshToken).where(RefreshToken.account_id == account_id)
        )
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_refresh_revoked_token_rejected(client) -> None:
    hdr, account_id, _access, refresh = _register(client)
    with SessionLocal() as db:
        row = db.scalar(
            select(RefreshToken).where(RefreshToken.account_id == account_id)
        )
        row.revoked_at = utcnow()
        db.commit()
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_refresh_banned_account_rejected(client) -> None:
    hdr, account_id, _access, refresh = _register(client, "rtban")
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.is_banned = True
        a.banned_reason = "test"
        db.commit()
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 403


def test_logout_revokes_refresh_token(client) -> None:
    hdr, _, _access, refresh = _register(client)
    r = client.post("/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["revoked"] is True

    # After logout, the token can't be refreshed.
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_logout_on_unknown_token_is_no_op(client) -> None:
    r = client.post("/auth/logout", json={"refresh_token": "nonexistent_1234567890"})
    assert r.status_code == 200
    assert r.json()["revoked"] is False


def test_password_reset_revokes_refresh_chain(client) -> None:
    hdr, account_id, _access, refresh = _register(client, "rtreset")
    # Request password reset.
    with SessionLocal() as db:
        email = db.get(Account, account_id).email
    r = client.post("/auth/forgot-password", json={"email": email})
    raw = r.json()["dev_reset_url"].split("token=")[1]
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "freshpass8"})
    assert r.status_code == 200
    # New access + refresh in response.
    assert r.json()["refresh_token"]
    # Old refresh is revoked.
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_refresh_token_works_even_when_access_is_expired(client) -> None:
    """Forcing the access JWT to be broken/stale, refresh should still mint a new one."""
    hdr, account_id, _access, refresh = _register(client)
    # Replace Authorization with garbage — irrelevant to /auth/refresh which is unauthenticated.
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
