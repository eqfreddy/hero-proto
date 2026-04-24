"""TOTP 2FA: enroll, confirm, disable, login challenge flow, verify."""

from __future__ import annotations

import random

import pyotp

from app.db import SessionLocal
from app.models import Account


def _register(client, prefix: str = "tp") -> tuple[str, dict, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return email, hdr, me["id"]


def _set_totp_enabled(account_id: int, secret: str) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.totp_secret = secret
        a.totp_enabled = True
        db.commit()


def test_enroll_returns_secret_and_uri(client) -> None:
    email, hdr, account_id = _register(client)
    r = client.post("/auth/2fa/enroll", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["secret"]
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert "hero-proto" in body["otpauth_uri"]
    # The local-part may be URL-encoded ("+" → "%2B") — check a stable prefix.
    local_prefix = email.split("@")[0].split("+")[0]
    assert local_prefix in body["otpauth_uri"]

    # Secret persisted, but totp_enabled still False (pending confirmation).
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        assert a.totp_secret == body["secret"]
        assert a.totp_enabled is False


def test_enroll_rejects_already_enabled(client) -> None:
    email, hdr, account_id = _register(client)
    # Enroll + confirm.
    r = client.post("/auth/2fa/enroll", headers=hdr)
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/auth/2fa/confirm", json={"code": code}, headers=hdr)
    # Second enroll attempt should 409.
    r = client.post("/auth/2fa/enroll", headers=hdr)
    assert r.status_code == 409


def test_confirm_wrong_code_rejected(client) -> None:
    email, hdr, _ = _register(client)
    client.post("/auth/2fa/enroll", headers=hdr)
    r = client.post("/auth/2fa/confirm", json={"code": "000000"}, headers=hdr)
    assert r.status_code == 400


def test_confirm_correct_code_enables(client) -> None:
    email, hdr, account_id = _register(client)
    r = client.post("/auth/2fa/enroll", headers=hdr)
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/auth/2fa/confirm", json={"code": code}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    with SessionLocal() as db:
        assert db.get(Account, account_id).totp_enabled is True


def test_confirm_without_enroll_rejected(client) -> None:
    email, hdr, _ = _register(client)
    r = client.post("/auth/2fa/confirm", json={"code": "000000"}, headers=hdr)
    assert r.status_code == 400
    assert "no pending 2fa enrollment" in r.text.lower()


def test_status_reflects_state(client) -> None:
    email, hdr, account_id = _register(client)
    assert client.get("/auth/2fa/status", headers=hdr).json()["enabled"] is False
    _set_totp_enabled(account_id, pyotp.random_base32())
    assert client.get("/auth/2fa/status", headers=hdr).json()["enabled"] is True


def test_login_without_totp_returns_tokens(client) -> None:
    email, hdr, _ = _register(client)
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    body = r.json()
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"]


def test_login_with_totp_returns_challenge(client) -> None:
    email, hdr, account_id = _register(client, "tplc")
    _set_totp_enabled(account_id, pyotp.random_base32())
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    body = r.json()
    assert body["status"] == "totp_required"
    assert body["challenge_token"]
    # No access/refresh in the challenge response.
    assert "access_token" not in body or not body.get("access_token")


def test_totp_verify_happy_path(client) -> None:
    email, hdr, account_id = _register(client, "tpv")
    secret = pyotp.random_base32()
    _set_totp_enabled(account_id, secret)

    login = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    challenge = login.json()["challenge_token"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/auth/2fa/verify", json={"challenge_token": challenge, "code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]

    # The new access token signs requests.
    r = client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert r.status_code == 200


def test_totp_verify_wrong_code_rejected(client) -> None:
    email, hdr, account_id = _register(client, "tpvw")
    secret = pyotp.random_base32()
    _set_totp_enabled(account_id, secret)
    login = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    challenge = login.json()["challenge_token"]
    r = client.post("/auth/2fa/verify", json={"challenge_token": challenge, "code": "000000"})
    assert r.status_code == 400


def test_totp_verify_invalid_challenge_rejected(client) -> None:
    # >16 chars so it passes the Pydantic min_length validator and reaches the decode path.
    r = client.post(
        "/auth/2fa/verify",
        json={"challenge_token": "a" * 40 + ".b" * 40 + ".c" * 20, "code": "123456"},
    )
    assert r.status_code == 401


def test_disable_requires_code(client) -> None:
    email, hdr, account_id = _register(client, "tpd")
    secret = pyotp.random_base32()
    _set_totp_enabled(account_id, secret)

    # Wrong code.
    r = client.post("/auth/2fa/disable", json={"code": "000000"}, headers=hdr)
    assert r.status_code == 400
    with SessionLocal() as db:
        assert db.get(Account, account_id).totp_enabled is True

    # Correct code.
    r = client.post("/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        assert a.totp_enabled is False
        assert a.totp_secret == "", "secret should be cleared on disable"


def test_banned_user_cannot_complete_2fa_login(client) -> None:
    email, hdr, account_id = _register(client, "tpban")
    secret = pyotp.random_base32()
    _set_totp_enabled(account_id, secret)

    # Login gets challenge.
    login = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    # Should actually 403 at login when banned…
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.is_banned = True
        a.banned_reason = "test"
        db.commit()

    # Re-login: banned.
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    assert r.status_code == 403

    # Even if the challenge was issued before the ban, verify refuses.
    challenge = login.json()["challenge_token"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/auth/2fa/verify", json={"challenge_token": challenge, "code": code})
    assert r.status_code == 403
