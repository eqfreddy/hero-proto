"""Store: product listing, mock purchase grants, idempotency, limits, refund."""

from __future__ import annotations

import random

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, LedgerDirection, Purchase, PurchaseLedger, PurchaseState


def _register(client, prefix: str = "shop") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _promote_to_admin(account_id: int) -> None:
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        a.is_admin = True
        db.commit()


def test_list_products_returns_seeded_catalog(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/shop/products", headers=hdr)
    assert r.status_code == 200
    skus = {p["sku"] for p in r.json()}
    # Seeded set (see SHOP_SEEDS).
    assert {"starter_pack", "gems_small", "gems_medium", "gems_large", "access_cards_pack"} <= skus


def test_mock_purchase_grants_currencies(client) -> None:
    hdr, account_id = _register(client)
    before = client.get("/me", headers=hdr).json()
    r = client.post("/shop/purchases", json={"sku": "gems_small"}, headers=hdr)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["state"] == "COMPLETED"
    assert p["granted"]["gems"] == 300
    assert p["price_cents_paid"] == 499

    after = client.get("/me", headers=hdr).json()
    assert after["gems"] == before["gems"] + 300


def test_starter_pack_one_time_limit(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/shop/purchases", json={"sku": "starter_pack"}, headers=hdr)
    assert r.status_code == 201
    r = client.post("/shop/purchases", json={"sku": "starter_pack"}, headers=hdr)
    assert r.status_code == 409
    assert "limit" in r.text.lower()


def test_starter_pack_hidden_after_purchase(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/shop/purchases", json={"sku": "starter_pack"}, headers=hdr)
    assert r.status_code == 201
    # By default unavailable products are filtered out.
    r = client.get("/shop/products", headers=hdr)
    skus = {p["sku"] for p in r.json()}
    assert "starter_pack" not in skus
    # With include_unavailable=true, it appears but marked unavailable.
    r = client.get("/shop/products?include_unavailable=true", headers=hdr)
    starter = next(p for p in r.json() if p["sku"] == "starter_pack")
    assert starter["available"] is False
    assert starter["owned_count"] == 1


def test_purchase_idempotent_by_client_ref(client) -> None:
    hdr, _ = _register(client)
    before = client.get("/me", headers=hdr).json()
    ref = "dedupe-" + str(random.randint(1, 10**9))
    r1 = client.post("/shop/purchases", json={"sku": "gems_small", "client_ref": ref}, headers=hdr)
    r2 = client.post("/shop/purchases", json={"sku": "gems_small", "client_ref": ref}, headers=hdr)
    assert r1.status_code == 201
    # Second call returns the same purchase.
    assert r1.json()["id"] == r2.json()["id"]
    after = client.get("/me", headers=hdr).json()
    # Currency only granted once.
    assert after["gems"] == before["gems"] + 300


def test_unknown_sku_404(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/shop/purchases", json={"sku": "does_not_exist"}, headers=hdr)
    assert r.status_code == 404


def test_purchase_requires_auth(client) -> None:
    r = client.post("/shop/purchases", json={"sku": "gems_small"})
    assert r.status_code == 401


def test_purchases_mine_history(client) -> None:
    hdr, _ = _register(client)
    client.post("/shop/purchases", json={"sku": "gems_small"}, headers=hdr)
    client.post("/shop/purchases", json={"sku": "shards_pack"}, headers=hdr)
    r = client.get("/shop/purchases/mine", headers=hdr)
    assert r.status_code == 200
    skus = [p["sku"] for p in r.json()]
    # Newest-first.
    assert skus[:2] == ["shards_pack", "gems_small"]


def test_admin_refund_reverses_currency_and_marks_purchase(client) -> None:
    admin_hdr, admin_id = _register(client, "shopadm")
    _promote_to_admin(admin_id)
    buyer_hdr, buyer_id = _register(client, "buyer")

    buy = client.post("/shop/purchases", json={"sku": "gems_medium"}, headers=buyer_hdr).json()
    before = client.get(f"/admin/accounts/{buyer_id}", headers=admin_hdr).json()
    assert before["gems"] >= 1400

    r = client.post(
        f"/admin/purchases/{buy['id']}/refund",
        headers=admin_hdr, json={"reason": "chargeback"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "REFUNDED"
    assert r.json()["refund_reason"] == "chargeback"

    after = client.get(f"/admin/accounts/{buyer_id}", headers=admin_hdr).json()
    assert after["gems"] == before["gems"] - 1400

    # Ledger has GRANT + REFUND rows for gems.
    with SessionLocal() as db:
        rows = list(db.scalars(select(PurchaseLedger).where(PurchaseLedger.purchase_id == buy["id"])))
    directions = {(r.kind, r.direction) for r in rows}
    assert ("gems", LedgerDirection.GRANT) in directions
    assert ("gems", LedgerDirection.REFUND) in directions


def test_refund_twice_rejected(client) -> None:
    admin_hdr, admin_id = _register(client, "refundadm")
    _promote_to_admin(admin_id)
    buyer_hdr, _ = _register(client, "rbuyer")
    buy = client.post("/shop/purchases", json={"sku": "gems_small"}, headers=buyer_hdr).json()
    client.post(f"/admin/purchases/{buy['id']}/refund", headers=admin_hdr, json={})
    r = client.post(f"/admin/purchases/{buy['id']}/refund", headers=admin_hdr, json={})
    assert r.status_code == 409


def test_refund_clawback_clamps_to_zero(client) -> None:
    """If the player spent down paid currency below the refund amount, balance goes to 0 not negative."""
    admin_hdr, admin_id = _register(client, "clampadm")
    _promote_to_admin(admin_id)
    buyer_hdr, buyer_id = _register(client, "clamp")

    buy = client.post("/shop/purchases", json={"sku": "gems_small"}, headers=buyer_hdr).json()
    # Drain the buyer's gems below the grant amount.
    with SessionLocal() as db:
        a = db.get(Account, buyer_id)
        a.gems = 50  # was at least 300 from the grant; now less than the grant amount
        db.commit()

    r = client.post(f"/admin/purchases/{buy['id']}/refund", headers=admin_hdr, json={})
    assert r.status_code == 200

    after = client.get(f"/admin/accounts/{buyer_id}", headers=admin_hdr).json()
    assert after["gems"] == 0  # clamped, not negative


def test_admin_purchase_list_filters(client) -> None:
    admin_hdr, admin_id = _register(client, "listadm")
    _promote_to_admin(admin_id)
    buyer_hdr, buyer_id = _register(client, "lbuyer")
    client.post("/shop/purchases", json={"sku": "gems_small"}, headers=buyer_hdr)
    client.post("/shop/purchases", json={"sku": "shards_pack"}, headers=buyer_hdr)

    r = client.get(f"/admin/purchases?account_id={buyer_id}", headers=admin_hdr)
    assert r.status_code == 200
    got = r.json()
    assert len(got) == 2
    assert all(p["account_id"] == buyer_id for p in got)

    r = client.get("/admin/purchases?state=COMPLETED", headers=admin_hdr)
    assert r.status_code == 200
    assert all(p["state"] == "COMPLETED" for p in r.json())


def test_mock_payments_disabled_returns_403(client, monkeypatch) -> None:
    """When HEROPROTO_MOCK_PAYMENTS_ENABLED is off, the mock endpoint refuses."""
    from app.config import settings
    monkeypatch.setattr(settings, "mock_payments_enabled", False)
    hdr, _ = _register(client)
    r = client.post("/shop/purchases", json={"sku": "gems_small"}, headers=hdr)
    assert r.status_code == 403


def test_purchase_records_processor_and_ledger_entries(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/shop/purchases", json={"sku": "access_cards_pack"}, headers=hdr)
    assert r.status_code == 201
    pid = r.json()["id"]

    with SessionLocal() as db:
        p = db.get(Purchase, pid)
        assert p.processor == "mock"
        assert p.state == PurchaseState.COMPLETED
        ledger = list(db.scalars(select(PurchaseLedger).where(PurchaseLedger.purchase_id == pid)))

    # Should have one GRANT row for access_cards.
    grants = [l for l in ledger if l.direction == LedgerDirection.GRANT]
    assert len(grants) == 1
    assert grants[0].kind == "access_cards"
    assert grants[0].amount == 15
