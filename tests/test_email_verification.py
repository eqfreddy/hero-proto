"""Email verification: send-verification + verify-email, token hygiene, idempotency."""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, EmailVerificationToken, utcnow
from app.routers.auth import _hash_token


def _register(client, prefix: str = "ev") -> tuple[str, dict[str, str], int]:
    """Returns (email, hdr, account_id)."""
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return email, hdr, me["id"]


def test_new_account_is_unverified_by_default(client) -> None:
    email, _hdr, account_id = _register(client)
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        assert a.email_verified is False
        assert a.email_verified_at is None


def test_send_verification_issues_token_with_dev_url(client) -> None:
    email, hdr, account_id = _register(client)
    r = client.post("/auth/send-verification", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_verified"] is False
    assert body["dev_verify_url"] is not None
    assert body["dev_verify_url"].startswith("/auth/verify-email?token=")

    # Hashed row landed in DB.
    raw = body["dev_verify_url"].split("token=")[1]
    with SessionLocal() as db:
        rows = db.scalars(
            select(EmailVerificationToken).where(EmailVerificationToken.account_id == account_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].token_hash == _hash_token(raw)


def test_verify_email_happy_path(client) -> None:
    email, hdr, account_id = _register(client)
    r = client.post("/auth/send-verification", headers=hdr)
    raw = r.json()["dev_verify_url"].split("token=")[1]

    # No auth needed on verify — holding the token is the proof.
    r = client.post("/auth/verify-email", json={"token": raw})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verified"
    assert r.json()["email"] == email

    # Account now shows verified.
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        assert a.email_verified is True
        assert a.email_verified_at is not None


def test_send_verification_idempotent_after_verified(client) -> None:
    email, hdr, account_id = _register(client)
    r = client.post("/auth/send-verification", headers=hdr)
    raw = r.json()["dev_verify_url"].split("token=")[1]
    client.post("/auth/verify-email", json={"token": raw})

    # Second send returns already_verified=true, no new token row.
    with SessionLocal() as db:
        before = db.scalars(
            select(EmailVerificationToken).where(EmailVerificationToken.account_id == account_id)
        ).all()
    r = client.post("/auth/send-verification", headers=hdr)
    assert r.status_code == 200
    assert r.json()["already_verified"] is True
    assert r.json()["dev_verify_url"] is None
    with SessionLocal() as db:
        after = db.scalars(
            select(EmailVerificationToken).where(EmailVerificationToken.account_id == account_id)
        ).all()
    assert len(after) == len(before), "shouldn't issue another token when already verified"


def test_verify_email_used_token_rejected(client) -> None:
    email, hdr, _ = _register(client)
    r = client.post("/auth/send-verification", headers=hdr)
    raw = r.json()["dev_verify_url"].split("token=")[1]
    client.post("/auth/verify-email", json={"token": raw})
    # Second use — 409.
    r = client.post("/auth/verify-email", json={"token": raw})
    assert r.status_code == 409


def test_verify_email_expired_token_rejected(client) -> None:
    email, hdr, account_id = _register(client)
    r = client.post("/auth/send-verification", headers=hdr)
    raw = r.json()["dev_verify_url"].split("token=")[1]

    # Push expiry to the past.
    with SessionLocal() as db:
        row = db.scalar(
            select(EmailVerificationToken).where(EmailVerificationToken.account_id == account_id)
        )
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()

    r = client.post("/auth/verify-email", json={"token": raw})
    assert r.status_code == 410


def test_verify_unknown_token_rejected(client) -> None:
    r = client.post(
        "/auth/verify-email",
        json={"token": "definitely_not_a_real_verification_token"},
    )
    assert r.status_code == 400


def test_send_verification_requires_auth(client) -> None:
    r = client.post("/auth/send-verification")
    assert r.status_code == 401


def test_verified_only_gate_rejects_unverified(client) -> None:
    """Smoke: the get_current_account_verified_only dep produces 403 for unverified accounts."""
    # We don't gate any live endpoints on this dep today, so we assemble a tiny
    # in-process test using FastAPI's dependency_overrides.
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from app.routers.auth import get_current_account_verified_only
    from app.main import app as real_app  # noqa: F401 — imported so deps graph compiles
    from typing import Annotated

    app = FastAPI()

    @app.get("/gated")
    def gated(account: Annotated[Account, Depends(get_current_account_verified_only)]) -> dict:
        return {"email": account.email}

    # Share deps with the real app so auth flow works.
    from app.deps import get_current_account
    from app.db import get_db as real_get_db

    client_inner = TestClient(app)

    # Register + hit without verifying → 403.
    email, hdr, account_id = _register(client, "gated")

    # Simulate: inject the same auth behavior. We actually need the real app's
    # get_current_account to resolve from our JWT. Simpler: use the main app
    # and just add a test route that uses the verified gate.
    real_app.dependency_overrides = {}
    # Add a temporary route at runtime for this test.
    try:
        real_app.add_api_route(
            "/_test_gated", gated, methods=["GET"],
            dependencies=[Depends(get_current_account_verified_only)],
        )
    except Exception:
        pass
    r = client.get("/_test_gated", headers=hdr)
    # Accept 403 (verified required) OR 404 (route add didn't take) — we're really
    # just verifying the dep itself doesn't crash. Use a direct-call approach below.
    from fastapi import HTTPException
    import pytest
    with SessionLocal() as db:
        acct = db.get(Account, account_id)
        assert acct.email_verified is False
        with pytest.raises(HTTPException) as exc_info:
            get_current_account_verified_only(acct)
        assert exc_info.value.status_code == 403
