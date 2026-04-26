"""POST /me/password — authenticated password change."""

from __future__ import annotations

import random


def _register(client, prefix: str = "cp") -> tuple[str, str, str]:
    """Returns (email, access_token, refresh_token)."""
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    body = r.json()
    return email, body["access_token"], body["refresh_token"]


def test_change_password_succeeds_and_rotates_credentials(client) -> None:
    """Happy path: correct current password + valid new password yields a fresh
    access + refresh token pair."""
    email, access, refresh_old = _register(client)
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "MoreSecure123"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["access_token"] != access
    assert body["refresh_token"] and body["refresh_token"] != refresh_old


def test_change_password_kills_old_access_token(client) -> None:
    """After change, the old JWT should be rejected (token_version bumped)."""
    _email, access_old, _refresh_old = _register(client, "cpkill")
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "MoreSecure123"},
        headers={"Authorization": f"Bearer {access_old}"},
    )
    assert r.status_code == 200
    # Old access token must now 401.
    r = client.get("/me", headers={"Authorization": f"Bearer {access_old}"})
    assert r.status_code == 401


def test_change_password_kills_old_refresh_token(client) -> None:
    """After change, the old refresh chain must not rotate."""
    _email, access_old, refresh_old = _register(client, "cpref")
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "MoreSecure123"},
        headers={"Authorization": f"Bearer {access_old}"},
    )
    assert r.status_code == 200
    r = client.post("/auth/refresh", json={"refresh_token": refresh_old})
    assert r.status_code == 401


def test_change_password_new_token_pair_works(client) -> None:
    """The fresh access + refresh returned by the change must be usable."""
    _email, access_old, _ = _register(client, "cpnew")
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "MoreSecure123"},
        headers={"Authorization": f"Bearer {access_old}"},
    )
    body = r.json()
    new_access = body["access_token"]
    new_refresh = body["refresh_token"]
    # /me works with the new access token.
    r = client.get("/me", headers={"Authorization": f"Bearer {new_access}"})
    assert r.status_code == 200
    # Refresh works with the new refresh token.
    r = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert r.status_code == 200


def test_change_password_login_with_new_password_works(client) -> None:
    """End-to-end: after change, /auth/login accepts the new password."""
    email, access, _ = _register(client, "cplogin")
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "MoreSecure123"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    # Old password rejected.
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    assert r.status_code == 401
    # New password accepted.
    r = client.post("/auth/login", json={"email": email, "password": "MoreSecure123"})
    assert r.status_code == 200


def test_change_password_wrong_current_returns_401(client) -> None:
    """A stolen JWT is not enough — change requires proof of current secret."""
    _email, access, _refresh = _register(client, "cpwrong")
    r = client.post(
        "/me/password",
        json={"current_password": "wrongguess", "new_password": "MoreSecure123"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 401
    assert "current password" in r.json()["detail"].lower()


def test_change_password_same_as_current_returns_400(client) -> None:
    """Fat-finger guard — picking the same password silently logs you out
    elsewhere without changing anything. Reject explicitly."""
    _email, access, _refresh = _register(client, "cpsame")
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "hunter22"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 400


def test_change_password_too_short_returns_422(client) -> None:
    """Pydantic constraint enforces min_length=8 on the new password."""
    _email, access, _refresh = _register(client, "cpshort")
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "short"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 422


def test_change_password_requires_auth(client) -> None:
    r = client.post(
        "/me/password",
        json={"current_password": "hunter22", "new_password": "MoreSecure123"},
    )
    assert r.status_code == 401
