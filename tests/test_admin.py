"""Slice 19/62 — admin router: grant, ban/unban, promote, liveops CRUD, stats, auth gate."""

from __future__ import annotations

import random

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account


def _register(client, prefix: str = "adm") -> tuple[dict[str, str], str, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, token, me["id"]


def _promote_to_admin(account_id: int) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.is_admin = True
        db.commit()


def test_non_admin_gets_403_on_admin_endpoints(client) -> None:
    hdr, _, _ = _register(client, "plain")
    for path in ("/admin/accounts", "/admin/stats"):
        r = client.get(path, headers=hdr)
        assert r.status_code == 403, f"{path} should be 403, got {r.status_code}"


def test_admin_can_list_and_get_accounts(client) -> None:
    hdr, _, admin_id = _register(client, "adm")
    _promote_to_admin(admin_id)

    r = client.get("/admin/accounts", headers=hdr)
    assert r.status_code == 200
    rows = r.json()
    assert any(row["id"] == admin_id for row in rows)

    r = client.get(f"/admin/accounts/{admin_id}", headers=hdr)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_admin_grant_adds_resources_and_hero(client) -> None:
    hdr, _, admin_id = _register(client, "granter")
    _promote_to_admin(admin_id)
    _, _, victim_id = _register(client, "recipient")

    before = client.get(f"/admin/accounts/{victim_id}", headers=hdr).json()
    r = client.post(
        f"/admin/accounts/{victim_id}/grant",
        headers=hdr,
        json={"gems": 50, "coins": 1000, "shards": 5, "energy": 10},
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["gems"] == before["gems"] + 50
    assert after["coins"] == before["coins"] + 1000
    assert after["shards"] == before["shards"] + 5
    assert after["energy_stored"] == before["energy_stored"] + 10


def test_admin_ban_blocks_future_requests(client) -> None:
    hdr, _, admin_id = _register(client, "banner")
    _promote_to_admin(admin_id)
    victim_hdr, _, victim_id = _register(client, "naughty")

    # Victim can reach /me before ban.
    assert client.get("/me", headers=victim_hdr).status_code == 200

    r = client.post(
        f"/admin/accounts/{victim_id}/ban", headers=hdr, json={"reason": "cheating"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_banned"] is True
    assert r.json()["banned_reason"] == "cheating"

    # Existing JWT is rejected — the deps layer checks is_banned on every call.
    blocked = client.get("/me", headers=victim_hdr)
    assert blocked.status_code == 403
    assert "banned" in blocked.text.lower()

    # Unban restores access.
    r = client.post(f"/admin/accounts/{victim_id}/unban", headers=hdr)
    assert r.status_code == 200
    assert r.json()["is_banned"] is False
    assert client.get("/me", headers=victim_hdr).status_code == 200


def test_admin_cannot_ban_self(client) -> None:
    hdr, _, admin_id = _register(client, "selfban")
    _promote_to_admin(admin_id)
    r = client.post(f"/admin/accounts/{admin_id}/ban", headers=hdr, json={"reason": "oops"})
    assert r.status_code == 400


def test_admin_promote_makes_another_user_admin(client) -> None:
    hdr, _, admin_id = _register(client, "maker")
    _promote_to_admin(admin_id)
    _, _, new_id = _register(client, "recruit")

    r = client.post(f"/admin/accounts/{new_id}/promote", headers=hdr)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_admin_liveops_create_and_cancel(client) -> None:
    hdr, _, admin_id = _register(client, "ops")
    _promote_to_admin(admin_id)

    r = client.post(
        "/admin/liveops",
        headers=hdr,
        json={
            "kind": "DOUBLE_REWARDS",
            "name": "test weekend",
            "duration_hours": 4,
            "payload": {"multiplier": 2.0},
        },
    )
    assert r.status_code == 201, r.text
    event_id = r.json()["id"]

    # Show up in /liveops/active while running.
    active = client.get("/liveops/active").json()
    assert any(e["id"] == event_id for e in active)

    r = client.delete(f"/admin/liveops/{event_id}", headers=hdr)
    assert r.status_code == 200
    assert r.json()["cancelled_id"] == event_id

    # After cancel, event ends_at was set to now — no longer active.
    active_after = client.get("/liveops/active").json()
    assert not any(e["id"] == event_id for e in active_after)


def test_admin_stats_shape(client) -> None:
    hdr, _, admin_id = _register(client, "stats")
    _promote_to_admin(admin_id)
    r = client.get("/admin/stats", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    for key in ("accounts_total", "accounts_banned", "heroes_total", "battles_last_24h", "active_liveops"):
        assert key in body, f"missing {key}: {body}"
        assert isinstance(body[key], int)
    assert body["accounts_total"] >= 1
