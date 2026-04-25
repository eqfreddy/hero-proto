"""Password reset: forgot → reset flow, token hygiene, enumeration resistance."""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, PasswordResetToken, utcnow
from app.routers.auth import _hash_token


def _register(client, prefix: str = "pwr") -> tuple[str, int]:
    """Returns (email, account_id). Password is always 'hunter22'."""
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()
    return email, me["id"]


def test_forgot_password_always_200_even_for_unknown_email(client) -> None:
    """Enumeration resistance: unknown emails return the same shape as known ones."""
    r = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # No reset URL for non-existent accounts.
    assert body["dev_reset_url"] is None


def test_forgot_password_for_known_email_creates_token_and_returns_dev_url(client) -> None:
    email, account_id = _register(client, "pwrknown")
    r = client.post("/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    body = r.json()
    # In test env (HEROPROTO_ENVIRONMENT=test, != prod), the dev URL is exposed.
    assert body["dev_reset_url"] is not None
    # The link points at the user-facing /reset-password page (not the JSON
    # POST endpoint at /auth/reset-password). Page extracts token from URL
    # and POSTs it to /auth/reset-password to actually flip the credential.
    assert body["dev_reset_url"].startswith("/reset-password?token=")

    # A hashed token row landed in the DB.
    with SessionLocal() as db:
        rows = db.scalars(
            select(PasswordResetToken).where(PasswordResetToken.account_id == account_id)
        ).all()
        assert len(rows) == 1
        # Raw token is never stored.
        raw_token = body["dev_reset_url"].split("token=")[1]
        assert rows[0].token_hash == _hash_token(raw_token)
        # Length check: hash is 64 hex chars (sha256).
        assert len(rows[0].token_hash) == 64


def test_reset_password_happy_path_signs_in_with_new_password(client) -> None:
    email, account_id = _register(client)
    r = client.post("/auth/forgot-password", json={"email": email})
    raw = r.json()["dev_reset_url"].split("token=")[1]

    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "newsecurepw"})
    assert r.status_code == 200, r.text
    new_token = r.json()["access_token"]
    assert new_token

    # Old password no longer works.
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    assert r.status_code == 401

    # New password works.
    r = client.post("/auth/login", json={"email": email, "password": "newsecurepw"})
    assert r.status_code == 200


def test_reset_revokes_outstanding_jwts(client) -> None:
    """After reset, pre-existing tokens should be rejected (token_version bumped)."""
    email, account_id = _register(client, "pwrtv")
    # Get the original JWT.
    login = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    old_hdr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/me", headers=old_hdr).status_code == 200

    # Reset the password.
    r = client.post("/auth/forgot-password", json={"email": email})
    raw = r.json()["dev_reset_url"].split("token=")[1]
    client.post("/auth/reset-password", json={"token": raw, "new_password": "newsecurepw"})

    # Old JWT — dead. 401, not 403 (token_version mismatch, not ban).
    r = client.get("/me", headers=old_hdr)
    assert r.status_code == 401


def test_used_token_cannot_be_reused(client) -> None:
    email, _ = _register(client, "pwronce")
    r = client.post("/auth/forgot-password", json={"email": email})
    raw = r.json()["dev_reset_url"].split("token=")[1]
    # First use works.
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "first_new_pw"})
    assert r.status_code == 200
    # Second use — 409.
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "second_new_pw"})
    assert r.status_code == 409
    assert "already used" in r.text.lower()


def test_expired_token_rejected(client) -> None:
    email, account_id = _register(client, "pwrexp")
    r = client.post("/auth/forgot-password", json={"email": email})
    raw = r.json()["dev_reset_url"].split("token=")[1]

    # Push the token's expiry into the past.
    with SessionLocal() as db:
        tok = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.account_id == account_id)
        )
        tok.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()

    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "newsecurepw"})
    assert r.status_code == 410
    assert "expired" in r.text.lower()


def test_unknown_token_rejected(client) -> None:
    r = client.post(
        "/auth/reset-password",
        json={"token": "not_a_real_token_bytes_12345", "new_password": "whatever123"},
    )
    assert r.status_code == 400
    assert "invalid or unknown" in r.text.lower()


def test_short_password_rejected_by_validation(client) -> None:
    email, _ = _register(client, "pwrshort")
    r = client.post("/auth/forgot-password", json={"email": email})
    raw = r.json()["dev_reset_url"].split("token=")[1]
    r = client.post("/auth/reset-password", json={"token": raw, "new_password": "tiny"})
    assert r.status_code == 422  # pydantic min_length=8


def test_multiple_forgot_requests_create_multiple_tokens(client) -> None:
    """Spam resistance is handled at a higher layer (rate limit). Each request
    genuinely creates a fresh token — previous tokens stay valid until used/expired."""
    email, account_id = _register(client, "pwrmulti")
    for _ in range(3):
        r = client.post("/auth/forgot-password", json={"email": email})
        assert r.json()["dev_reset_url"] is not None
    with SessionLocal() as db:
        count = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.account_id == account_id)
        )
        assert count is not None  # at least one
        # Count rows — 3 requests = 3 tokens.
        all_rows = db.scalars(
            select(PasswordResetToken).where(PasswordResetToken.account_id == account_id)
        ).all()
        assert len(all_rows) == 3
