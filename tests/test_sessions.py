"""Active sessions / login history: list, single revoke, revoke-all."""

from __future__ import annotations

import random


def _register(client) -> tuple[str, str]:
    email = f"sess+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    j = r.json()
    return j["access_token"], j["refresh_token"]


def test_register_creates_a_session_visible_to_owner(client) -> None:
    access, _ = _register(client)
    hdr = {"Authorization": f"Bearer {access}"}
    r = client.get("/me/sessions", headers=hdr)
    assert r.status_code == 200, r.text
    sessions = r.json()
    assert len(sessions) == 1
    s = sessions[0]
    assert s["id"] > 0
    assert s["issued_at"]
    assert s["expires_at"]
    # IP + UA captured from the TestClient request.
    assert s["ip"] is not None
    assert s["user_agent"] is not None


def test_login_adds_a_second_session(client) -> None:
    access, _ = _register(client)
    email = client.get("/me", headers={"Authorization": f"Bearer {access}"}).json()["email"]

    # Login from the same client — second session.
    r = client.post("/auth/login", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    second_access = r.json()["access_token"]

    sessions = client.get(
        "/me/sessions",
        headers={"Authorization": f"Bearer {second_access}"},
    ).json()
    assert len(sessions) == 2


def test_revoke_one_session_kills_just_that_token(client) -> None:
    access1, refresh1 = _register(client)
    me_email = client.get("/me", headers={"Authorization": f"Bearer {access1}"}).json()["email"]
    r = client.post("/auth/login", json={"email": me_email, "password": "hunter22"})
    refresh2 = r.json()["refresh_token"]

    sessions = client.get(
        "/me/sessions",
        headers={"Authorization": f"Bearer {access1}"},
    ).json()
    assert len(sessions) == 2
    # Revoke the older one (lower id).
    target = min(s["id"] for s in sessions)
    r = client.post(
        f"/me/sessions/{target}/revoke",
        headers={"Authorization": f"Bearer {access1}"},
    )
    assert r.status_code == 200
    assert r.json()["revoked"] is True

    # The revoked refresh token must no longer rotate.
    r = client.post("/auth/refresh", json={"refresh_token": refresh1})
    assert r.status_code == 401
    # The other refresh still works.
    r = client.post("/auth/refresh", json={"refresh_token": refresh2})
    assert r.status_code == 200


def test_revoke_other_accounts_session_returns_404(client) -> None:
    alice_access, _ = _register(client)
    bob_access, _ = _register(client)
    # Find bob's session id.
    bob_sessions = client.get(
        "/me/sessions",
        headers={"Authorization": f"Bearer {bob_access}"},
    ).json()
    bob_sid = bob_sessions[0]["id"]
    # Alice tries to kill it.
    r = client.post(
        f"/me/sessions/{bob_sid}/revoke",
        headers={"Authorization": f"Bearer {alice_access}"},
    )
    assert r.status_code == 404


def test_revoke_all_invalidates_existing_access_tokens(client) -> None:
    access, refresh = _register(client)
    hdr = {"Authorization": f"Bearer {access}"}

    # Confirm /me works.
    assert client.get("/me", headers=hdr).status_code == 200

    r = client.post("/me/sessions/revoke-all", headers=hdr)
    assert r.status_code == 200
    assert r.json()["revoked"] >= 1

    # The access token that made the call is now revoked too (token_version bumped).
    assert client.get("/me", headers=hdr).status_code == 401
    # The refresh token is dead too.
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
