"""Phase 2.4 — Apple StoreKit + Google Play Billing IAP + PoE2 QoL/cosmetic catalog.

Adapters in app/payment_adapters.py ship with a sandbox shortcut: any
receipt prefixed `fake-apple:{json}` / `fake-google:{json}` skips the
real SDK and validates structurally. Tests use those so we don't need
real Apple / Google credentials in CI.

Coverage:
- Apple round-trip: receipt → /shop/iap/apple → grant + ledger.
- Google round-trip: same, /shop/iap/google.
- SKU mismatch between the body and the receipt is rejected.
- Idempotency: same processor_ref doesn't double-grant.
- QoL unlock grants (auto_battle, extra_team_presets, etc.) flip the
  account's qol_unlocks_json and surface on /me.
- Cosmetic frame grants surface on /me.
- Slot bumps stack — buying the hero slot pack twice gives 2× slots.
- Restore-purchases: re-granting an owned QoL unlock is idempotent.
"""

from __future__ import annotations

import json
import random


def _register(client) -> tuple[dict, int]:
    email = f"iap+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _apple_receipt(sku: str, tx: str) -> str:
    return "fake-apple:" + json.dumps({"productId": sku, "transactionId": tx})


def _google_receipt(sku: str, order: str) -> str:
    return "fake-google:" + json.dumps({"productId": sku, "orderId": order})


# --- Apple StoreKit round-trip ----------------------------------------------


def test_apple_iap_grants_qol_unlock(client) -> None:
    hdr, _ = _register(client)
    receipt = _apple_receipt("qol_auto_battle", f"apple-tx-{random.randint(10**9, 10**10)}")
    r = client.post(
        "/shop/iap/apple",
        json={"sku": "qol_auto_battle", "receipt": receipt},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    assert r.json()["state"] == "COMPLETED"
    assert r.json()["processor"] == "apple"

    me = client.get("/me", headers=hdr).json()
    assert "auto_battle" in me["qol_unlocks"]


def test_apple_iap_idempotent_on_same_transaction(client) -> None:
    """A second POST with the exact same receipt returns the existing
    Purchase row rather than double-granting."""
    hdr, _ = _register(client)
    tx = f"apple-tx-dup-{random.randint(10**9, 10**10)}"
    receipt = _apple_receipt("qol_quick_summon", tx)
    r1 = client.post("/shop/iap/apple", json={"sku": "qol_quick_summon", "receipt": receipt}, headers=hdr)
    assert r1.status_code == 201, r1.text
    pid = r1.json()["id"]

    r2 = client.post("/shop/iap/apple", json={"sku": "qol_quick_summon", "receipt": receipt}, headers=hdr)
    # Idempotent path returns a 201 with the *same* purchase id.
    assert r2.status_code == 201, r2.text
    assert r2.json()["id"] == pid

    # Account still owns the unlock exactly once.
    me = client.get("/me", headers=hdr).json()
    assert me["qol_unlocks"].count("quick_summon") == 1


def test_apple_iap_sku_mismatch_rejected(client) -> None:
    hdr, _ = _register(client)
    # Receipt claims a different product than the body.
    receipt = _apple_receipt("qol_auto_battle", f"apple-tx-{random.randint(10**9, 10**10)}")
    r = client.post(
        "/shop/iap/apple",
        json={"sku": "qol_quick_summon", "receipt": receipt},
        headers=hdr,
    )
    assert r.status_code == 400, r.text
    assert "sku" in r.text.lower()


# --- Google Play Billing round-trip -----------------------------------------


def test_google_iap_grants_cosmetic_frame(client) -> None:
    hdr, _ = _register(client)
    receipt = _google_receipt(
        "cosmetic_frame_neon",
        f"GPA.{random.randint(10**12, 10**13 - 1)}",
    )
    r = client.post(
        "/shop/iap/google",
        json={"sku": "cosmetic_frame_neon", "receipt": receipt},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    assert r.json()["processor"] == "google"

    me = client.get("/me", headers=hdr).json()
    assert "frame_neon_cubicle" in me["cosmetic_frames"]


def test_google_iap_extra_hero_slots_stack(client) -> None:
    """slots_hero_pack has per_account_limit=0 (stackable). Two purchases
    should add 50 slots."""
    hdr, _ = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    before_cap = me_before["hero_slot_cap"]

    for _ in range(2):
        receipt = _google_receipt(
            "slots_hero_pack",
            f"GPA.{random.randint(10**12, 10**13 - 1)}",
        )
        r = client.post(
            "/shop/iap/google",
            json={"sku": "slots_hero_pack", "receipt": receipt},
            headers=hdr,
        )
        assert r.status_code == 201, r.text

    me_after = client.get("/me", headers=hdr).json()
    assert me_after["hero_slot_cap"] == before_cap + 50, me_after


# --- Catalog correctness ----------------------------------------------------


def test_qol_catalog_uses_only_known_codes() -> None:
    """Every QoL / cosmetic SKU in the seed must reference a code that
    exists in app.store catalogs. Caught at seed time would be ideal,
    but a unit-level guard is cheap and prevents typo regressions."""
    from app.seed import SHOP_SEEDS
    from app.store import KNOWN_COSMETIC_FRAMES, KNOWN_QOL_UNLOCKS

    for p in SHOP_SEEDS:
        for code in (p["contents"].get("qol_unlocks") or []):
            assert code in KNOWN_QOL_UNLOCKS, f"unknown QoL code in seed {p['sku']}: {code}"
        for code in (p["contents"].get("cosmetic_frames") or []):
            assert code in KNOWN_COSMETIC_FRAMES, f"unknown frame in seed {p['sku']}: {code}"


def test_qol_unlock_restore_purchases_idempotent(client) -> None:
    """Granting a QoL unlock the player already owns must not create
    duplicate entries — covers the mobile restore-purchases path."""
    from app.db import SessionLocal
    from app.models import Account

    hdr, aid = _register(client)
    receipt = _apple_receipt("qol_auto_battle", f"apple-tx-{random.randint(10**9, 10**10)}")
    client.post("/shop/iap/apple", json={"sku": "qol_auto_battle", "receipt": receipt}, headers=hdr)

    # Wedge the same unlock through a second receipt (different processor_ref).
    receipt2 = _apple_receipt("qol_auto_battle", f"apple-tx-{random.randint(10**9, 10**10)}")
    r = client.post("/shop/iap/apple", json={"sku": "qol_auto_battle", "receipt": receipt2}, headers=hdr)
    assert r.status_code == 201, r.text

    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        owned = json.loads(a.qol_unlocks_json or "{}")
        # auto_battle present once. Timestamps don't multiply.
        assert list(owned.keys()).count("auto_battle") == 1
    finally:
        db.close()


# --- Refund coverage --------------------------------------------------------


def _promote_to_admin(account_id: int) -> None:
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, account_id)
        a.is_admin = True
        db.commit()
    finally:
        db.close()


def _register_admin(client) -> dict:
    email = f"iap-adm+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    _promote_to_admin(aid)
    return hdr


def test_iap_refund_revokes_qol_unlock(client) -> None:
    """Chargeback on an Apple QoL purchase must claw back the unlock —
    leaving auto-battle owned would be a free-money bug."""
    admin_hdr = _register_admin(client)
    buyer_hdr, _ = _register(client)

    receipt = _apple_receipt("qol_auto_battle", f"apple-tx-{random.randint(10**9, 10**10)}")
    buy = client.post(
        "/shop/iap/apple",
        json={"sku": "qol_auto_battle", "receipt": receipt},
        headers=buyer_hdr,
    ).json()

    me_pre = client.get("/me", headers=buyer_hdr).json()
    assert "auto_battle" in me_pre["qol_unlocks"]

    r = client.post(
        f"/admin/purchases/{buy['id']}/refund",
        headers=admin_hdr, json={"reason": "chargeback"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "REFUNDED"

    me_post = client.get("/me", headers=buyer_hdr).json()
    assert "auto_battle" not in me_post["qol_unlocks"], me_post


def test_iap_refund_revokes_cosmetic_frame(client) -> None:
    admin_hdr = _register_admin(client)
    buyer_hdr, _ = _register(client)

    receipt = _google_receipt(
        "cosmetic_frame_neon",
        f"GPA.{random.randint(10**12, 10**13 - 1)}",
    )
    buy = client.post(
        "/shop/iap/google",
        json={"sku": "cosmetic_frame_neon", "receipt": receipt},
        headers=buyer_hdr,
    ).json()
    assert "frame_neon_cubicle" in client.get("/me", headers=buyer_hdr).json()["cosmetic_frames"]

    client.post(f"/admin/purchases/{buy['id']}/refund", headers=admin_hdr, json={})
    me_post = client.get("/me", headers=buyer_hdr).json()
    assert "frame_neon_cubicle" not in me_post["cosmetic_frames"]


def test_iap_refund_clawback_slot_cap_floors_at_seeded_default(client) -> None:
    """Refund slots_hero_pack must not push the cap below the 50-slot
    seeded default. A player whose roster grew past 50 isn't punished
    by a chargeback."""
    admin_hdr = _register_admin(client)
    buyer_hdr, _ = _register(client)

    receipt = _google_receipt(
        "slots_hero_pack",
        f"GPA.{random.randint(10**12, 10**13 - 1)}",
    )
    buy = client.post(
        "/shop/iap/google",
        json={"sku": "slots_hero_pack", "receipt": receipt},
        headers=buyer_hdr,
    ).json()
    cap_after = client.get("/me", headers=buyer_hdr).json()["hero_slot_cap"]
    assert cap_after == 75  # 50 default + 25 from pack

    client.post(f"/admin/purchases/{buy['id']}/refund", headers=admin_hdr, json={})
    cap_post = client.get("/me", headers=buyer_hdr).json()["hero_slot_cap"]
    assert cap_post == 50  # back to seeded default, not lower


def test_unknown_qol_code_in_product_raises_value_error() -> None:
    """If a product is misconfigured to grant a code we don't know
    about, apply_grant raises ValueError so the typo blows up loudly
    rather than silently no-op'ing."""
    from app.db import SessionLocal
    from app.models import Account, Purchase, PurchaseState, ShopProduct
    from app.store import apply_grant

    db = SessionLocal()
    try:
        # Fake purchase / product — never persisted, just shape carriers.
        a = db.query(Account).first()
        if a is None:
            import pytest
            pytest.skip("no account in DB; this is a unit-level guard")
        purchase = Purchase(
            account_id=a.id, sku="x", title_snapshot="x",
            price_cents_paid=0, currency_code="USD", processor="mock",
            processor_ref=f"unit-{random.randint(10**9, 10**10)}",
            state=PurchaseState.PENDING,
        )
        db.add(purchase)
        db.flush()
        try:
            apply_grant(db, a, purchase, {"qol_unlocks": ["does_not_exist"]})
            raise AssertionError("expected ValueError on unknown QoL code")
        except ValueError as e:
            assert "does_not_exist" in str(e)
        db.rollback()
    finally:
        db.close()
