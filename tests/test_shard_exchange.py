"""Shard store — gems → shards exchange endpoint."""

from __future__ import annotations

import random

from app.config import settings
from app.db import SessionLocal
from app.models import Account


def _register_with_gems(client, gems: int) -> dict[str, str]:
    email = f"sx+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    with SessionLocal() as db:
        a = db.get(Account, me["id"])
        a.gems = gems
        db.commit()
    return hdr


def test_status_for_fresh_account(client) -> None:
    hdr = _register_with_gems(client, 0)
    r = client.get("/shop/shard-exchange", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["gems_per_batch"] == settings.shard_exchange_gems_per_batch
    assert body["shards_per_batch"] == settings.shard_exchange_shards_per_batch
    assert body["max_per_day"] == settings.shard_exchange_max_per_day
    assert body["used_today"] == 0
    assert body["remaining_today"] == settings.shard_exchange_max_per_day


def test_single_batch_swap(client) -> None:
    hdr = _register_with_gems(client, 100)
    r = client.post("/shop/shard-exchange", json={"batches": 1}, headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["gems_spent"] == settings.shard_exchange_gems_per_batch
    assert body["shards_gained"] == settings.shard_exchange_shards_per_batch
    assert body["gems"] == 100 - settings.shard_exchange_gems_per_batch
    # Shards may be > shards_per_batch if account starts with starter shards.
    assert body["used_today"] == 1
    assert body["remaining_today"] == settings.shard_exchange_max_per_day - 1


def test_multi_batch_atomic(client) -> None:
    hdr = _register_with_gems(client, settings.shard_exchange_gems_per_batch * 5)
    r = client.post("/shop/shard-exchange", json={"batches": 5}, headers=hdr)
    assert r.status_code == 201
    body = r.json()
    assert body["batches"] == 5
    assert body["gems"] == 0  # consumed exactly all gems
    assert body["used_today"] == 5


def test_insufficient_gems_409(client) -> None:
    hdr = _register_with_gems(client, settings.shard_exchange_gems_per_batch - 1)
    r = client.post("/shop/shard-exchange", json={"batches": 1}, headers=hdr)
    assert r.status_code == 409
    assert "not enough gems" in r.json()["detail"].lower()


def test_daily_cap_enforced(client) -> None:
    cap = settings.shard_exchange_max_per_day
    gems_needed = settings.shard_exchange_gems_per_batch * (cap + 1)
    hdr = _register_with_gems(client, gems_needed)
    # Exhaust the day's budget in one big request.
    r = client.post("/shop/shard-exchange", json={"batches": cap}, headers=hdr)
    assert r.status_code == 201
    assert r.json()["remaining_today"] == 0
    # Next batch fails.
    r = client.post("/shop/shard-exchange", json={"batches": 1}, headers=hdr)
    assert r.status_code == 409
    assert "limit" in r.json()["detail"].lower()


def test_request_exceeding_remaining_409(client) -> None:
    cap = settings.shard_exchange_max_per_day
    hdr = _register_with_gems(client, settings.shard_exchange_gems_per_batch * 10)
    # Use 5, then ask for cap (which exceeds remaining = cap - 5).
    client.post("/shop/shard-exchange", json={"batches": 5}, headers=hdr)
    r = client.post("/shop/shard-exchange", json={"batches": cap}, headers=hdr)
    assert r.status_code == 409
    assert "only allows" in r.json()["detail"].lower()


def test_pydantic_rejects_oversize(client) -> None:
    hdr = _register_with_gems(client, 99999)
    # batches > 20 should 422 from Field validation
    r = client.post("/shop/shard-exchange", json={"batches": 999}, headers=hdr)
    assert r.status_code == 422


def test_zero_or_negative_rejected(client) -> None:
    hdr = _register_with_gems(client, 99999)
    r = client.post("/shop/shard-exchange", json={"batches": 0}, headers=hdr)
    assert r.status_code == 422
    r = client.post("/shop/shard-exchange", json={"batches": -1}, headers=hdr)
    assert r.status_code == 422
