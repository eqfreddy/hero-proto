"""Tests for the OfferBundle feature.

Covers:
- GET /shop/bundles (public listing)
- POST /shop/bundles/{code}/purchase (mock payment)
- GET /me/purchases (purchase history)
- one_per_account enforcement
- inactive bundle 404
- velocity limiting (6th purchase → 429)
- gem_pack_small purchasable twice (one_per_account=False)
- unauthenticated purchase → 401
"""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _register(client: TestClient) -> tuple[dict, int]:
    email = f"bundles+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


# ---------------------------------------------------------------------------
# 1. GET /shop/bundles — public, returns active seeded bundles
# ---------------------------------------------------------------------------


def test_list_bundles_returns_seeded_bundles(client: TestClient) -> None:
    r = client.get("/shop/bundles")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    codes = {b["code"] for b in data}
    # All four seeded bundles must appear.
    assert {"starter_pack", "gem_pack_small", "shard_surge", "vip_bundle"} <= codes


def test_list_bundles_no_auth_required(client: TestClient) -> None:
    """Bundles are publicly visible — no token needed."""
    r = client.get("/shop/bundles")
    assert r.status_code == 200, r.text


def test_list_bundles_contains_expected_fields(client: TestClient) -> None:
    r = client.get("/shop/bundles")
    assert r.status_code == 200
    bundles = {b["code"]: b for b in r.json()}
    vip = bundles["vip_bundle"]
    assert vip["price_usd"] == pytest.approx(9.99, abs=0.01)
    assert vip["gems"] == 500
    assert vip["shards"] == 50
    assert vip["access_cards"] == 10
    assert vip["one_per_account"] is True


# ---------------------------------------------------------------------------
# 2. POST /shop/bundles/{code}/purchase — mock payment grants currencies
# ---------------------------------------------------------------------------


def test_purchase_bundle_grants_currencies(client: TestClient) -> None:
    hdr, _ = _register(client)
    before = client.get("/me", headers=hdr).json()

    r = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["bundle_code"] == "gem_pack_small"
    assert body["gems_granted"] == 100
    assert body["price_usd"] == pytest.approx(1.99, abs=0.01)

    after = client.get("/me", headers=hdr).json()
    assert after["gems"] == before["gems"] + 100


def test_purchase_starter_pack_grants_gems_and_shards(client: TestClient) -> None:
    hdr, _ = _register(client)
    before = client.get("/me", headers=hdr).json()

    r = client.post("/shop/bundles/starter_pack/purchase", headers=hdr)
    assert r.status_code == 201, r.text

    after = client.get("/me", headers=hdr).json()
    assert after["gems"] == before["gems"] + 200
    assert after["shards"] == before["shards"] + 30


# ---------------------------------------------------------------------------
# 3. GET /me/purchases — purchase is recorded in history
# ---------------------------------------------------------------------------


def test_purchase_recorded_in_history(client: TestClient) -> None:
    hdr, _ = _register(client)

    r = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
    assert r.status_code == 201, r.text
    purchase_id = r.json()["id"]

    hist = client.get("/me/purchases", headers=hdr)
    assert hist.status_code == 200, hist.text
    body = hist.json()
    assert "purchases" in body
    assert "total" in body
    ids = [p["id"] for p in body["purchases"]]
    assert purchase_id in ids

    item = next(p for p in body["purchases"] if p["id"] == purchase_id)
    assert item["product_code"] == "bundle:gem_pack_small"
    assert item["amount_usd"] == pytest.approx(1.99, abs=0.01)
    assert item["payment_method"] == "mock-payment"


def test_purchase_history_pagination(client: TestClient) -> None:
    hdr, _ = _register(client)

    # Make 3 purchases (gem_pack_small, one_per_account=False)
    for _ in range(3):
        r = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
        assert r.status_code == 201, r.text

    hist = client.get("/me/purchases?limit=2&offset=0", headers=hdr)
    assert hist.status_code == 200
    body = hist.json()
    assert len(body["purchases"]) == 2
    assert body["total"] >= 3


# ---------------------------------------------------------------------------
# 4. one_per_account → 409 on second attempt
# ---------------------------------------------------------------------------


def test_one_per_account_returns_409(client: TestClient) -> None:
    hdr, _ = _register(client)

    r1 = client.post("/shop/bundles/starter_pack/purchase", headers=hdr)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/shop/bundles/starter_pack/purchase", headers=hdr)
    assert r2.status_code == 409, r2.text
    assert "once per account" in r2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Inactive / missing bundle → 404
# ---------------------------------------------------------------------------


def test_inactive_bundle_returns_404(client: TestClient) -> None:
    """Non-existent bundle code returns 404."""
    hdr, _ = _register(client)
    r = client.post("/shop/bundles/does_not_exist/purchase", headers=hdr)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 6. Velocity limit: 6th bundle purchase in one hour → 429
# ---------------------------------------------------------------------------


def test_velocity_limit_429_on_sixth_purchase(client: TestClient) -> None:
    """gem_pack_small has one_per_account=False so we can purchase it many
    times; the velocity gate should trip on the 6th attempt within 1 hour."""
    hdr, _ = _register(client)

    # First 5 must succeed.
    for i in range(5):
        r = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
        assert r.status_code == 201, f"purchase {i+1} failed: {r.text}"

    # 6th must be rejected.
    r = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
    assert r.status_code == 429, r.text
    assert "retry-after" in {k.lower() for k in r.headers}


# ---------------------------------------------------------------------------
# 7. gem_pack_small purchasable twice (one_per_account=False)
# ---------------------------------------------------------------------------


def test_gem_pack_small_purchasable_twice(client: TestClient) -> None:
    hdr, _ = _register(client)

    r1 = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/shop/bundles/gem_pack_small/purchase", headers=hdr)
    assert r2.status_code == 201, r2.text


# ---------------------------------------------------------------------------
# 8. Unauthenticated purchase → 401
# ---------------------------------------------------------------------------


def test_unauthenticated_purchase_returns_401(client: TestClient) -> None:
    r = client.post("/shop/bundles/gem_pack_small/purchase")
    assert r.status_code == 401, r.text


def test_unauthenticated_purchase_history_returns_401(client: TestClient) -> None:
    r = client.get("/me/purchases")
    assert r.status_code == 401, r.text
