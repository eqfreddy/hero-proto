"""Integration tests against the in-process FastAPI app (no network server)."""

from __future__ import annotations


def test_healthz(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_grants_starter_and_onboarding_bonus(client) -> None:
    r = client.post("/auth/register", json={"email": "starter@example.com", "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["shards"] >= 20  # 10 starter + 10 onboarding bonus
    assert me["energy"] == me["energy_cap"]
    # New premium currency defaults to 0 on fresh accounts.
    assert me["access_cards"] == 0


def test_full_loop(client, auth_headers) -> None:
    r = client.post("/summon/x10", headers=auth_headers)
    assert r.status_code == 201
    r = client.get("/heroes/mine", headers=auth_headers)
    roster = sorted(r.json(), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in roster[:3]]

    stages = client.get("/stages").json()
    stage1 = next(s for s in stages if s["order"] == 1)

    r = client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["outcome"] in ("WIN", "LOSS", "DRAW")


def test_dailies_roll_three(client, auth_headers) -> None:
    r = client.get("/daily", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_unauth_endpoints_reject(client) -> None:
    assert client.get("/me").status_code == 401
    assert client.get("/heroes/mine").status_code == 401
    assert client.post("/summon").status_code == 401


def test_summon_requires_shards(client) -> None:
    # Register, burn all shards, then expect 409 on another pull.
    r = client.post("/auth/register", json={"email": "broke@example.com", "password": "hunter22"})
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # 20 shards starter+onboarding → 2 x10 pulls max.
    client.post("/summon/x10", headers=hdr)
    client.post("/summon/x10", headers=hdr)
    r = client.post("/summon", headers=hdr)
    assert r.status_code == 409
