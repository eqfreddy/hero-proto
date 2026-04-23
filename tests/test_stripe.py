"""Stripe checkout + webhook tests.

We don't talk to Stripe here — we mock `stripe.checkout.Session.create` and
`stripe.Webhook.construct_event` so the flow can be validated without a real
merchant account. A real smoke test against Stripe test mode is a separate
manual step documented in docs/STRIPE_SETUP.md.
"""

from __future__ import annotations

import json
import random
from types import SimpleNamespace

import pytest
import stripe

from app.db import SessionLocal
from app.models import (
    Account,
    LedgerDirection,
    Purchase,
    PurchaseLedger,
    PurchaseState,
    ShopProduct,
)


@pytest.fixture()
def configured_stripe(monkeypatch):
    """Point settings at fake Stripe creds so _require_stripe_configured passes."""
    from app.config import settings
    monkeypatch.setattr(settings, "stripe_api_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    return settings


def _register(client, prefix: str = "stripe") -> tuple[dict[str, str], int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()
    return {"Authorization": f"Bearer {token}"}, me["id"]


def _set_stripe_price(sku: str, price_id: str) -> None:
    with SessionLocal() as db:
        p = db.query(ShopProduct).filter_by(sku=sku).one()
        p.stripe_price_id = price_id
        db.commit()


def test_checkout_requires_stripe_configured(client) -> None:
    """Without HEROPROTO_STRIPE_API_KEY, the endpoint 503s instead of leaking a 500."""
    hdr, _ = _register(client)
    r = client.post("/shop/checkout/stripe", json={"sku": "gems_small"}, headers=hdr)
    assert r.status_code == 503
    assert "STRIPE_API_KEY" in r.text


def test_checkout_rejects_product_without_price_id(client, configured_stripe) -> None:
    """If a seed product has no stripe_price_id, checkout must refuse — can't create session."""
    hdr, _ = _register(client)
    r = client.post("/shop/checkout/stripe", json={"sku": "gems_small"}, headers=hdr)
    assert r.status_code == 409
    assert "Stripe price" in r.text


def test_checkout_happy_path_creates_pending_purchase(client, configured_stripe, monkeypatch) -> None:
    _set_stripe_price("gems_small", "price_fake_123")
    hdr, account_id = _register(client)

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_test_abc123", url="https://stripe.test/session/abc123")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    r = client.post(
        "/shop/checkout/stripe",
        json={"sku": "gems_small", "client_ref": "ref-xyz"},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["checkout_url"] == "https://stripe.test/session/abc123"
    assert body["session_id"] == "cs_test_abc123"

    # Stripe.create called with our price + metadata.
    assert captured["line_items"] == [{"price": "price_fake_123", "quantity": 1}]
    assert captured["metadata"]["account_id"] == str(account_id)
    assert captured["metadata"]["sku"] == "gems_small"
    assert captured["client_reference_id"] == "ref-xyz"

    # Purchase row persisted in PENDING, keyed by the returned session id.
    with SessionLocal() as db:
        p = db.get(Purchase, body["purchase_id"])
        assert p is not None
        assert p.state == PurchaseState.PENDING
        assert p.processor == "stripe"
        assert p.processor_ref == "cs_test_abc123"


def test_checkout_stripe_error_rolls_back_pending(client, configured_stripe, monkeypatch) -> None:
    """If Stripe errors, the pending row is cleaned up so the same client_ref can retry."""
    _set_stripe_price("gems_small", "price_fake_err")
    hdr, _ = _register(client)

    def fake_create(**_):
        raise stripe.error.StripeError("boom")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    r = client.post(
        "/shop/checkout/stripe",
        json={"sku": "gems_small", "client_ref": "retry-me"},
        headers=hdr,
    )
    assert r.status_code == 502

    # No lingering pending row for that client_ref.
    with SessionLocal() as db:
        lingering = db.query(Purchase).filter(
            Purchase.processor == "stripe",
            Purchase.processor_ref == "pending:retry-me",
        ).all()
        assert not lingering


def test_webhook_rejects_missing_secret(client, monkeypatch) -> None:
    from app.config import settings
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    r = client.post("/shop/webhooks/stripe", content=b"{}", headers={"stripe-signature": "x"})
    assert r.status_code == 503


def test_webhook_rejects_invalid_signature(client, configured_stripe, monkeypatch) -> None:
    def fake_construct(**_):
        raise stripe.error.SignatureVerificationError("bad sig", "header")

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct)

    r = client.post(
        "/shop/webhooks/stripe",
        content=b'{"type":"checkout.session.completed"}',
        headers={"stripe-signature": "forged"},
    )
    assert r.status_code == 400
    assert "signature" in r.text.lower()


def test_webhook_rejects_malformed_payload(client, configured_stripe, monkeypatch) -> None:
    def fake_construct(**_):
        raise ValueError("not json")

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct)

    r = client.post(
        "/shop/webhooks/stripe", content=b"not json", headers={"stripe-signature": "x"},
    )
    assert r.status_code == 400


def test_webhook_completed_grants_and_is_idempotent(client, configured_stripe, monkeypatch) -> None:
    """checkout.session.completed should COMPLETE the pending purchase, grant contents,
    and be safe to deliver twice (Stripe retries on 5xx)."""
    _set_stripe_price("gems_small", "price_fake_ok")
    hdr, account_id = _register(client)

    # Create checkout to land a pending Purchase row tied to session 'cs_good'.
    monkeypatch.setattr(
        stripe.checkout.Session, "create",
        lambda **_: SimpleNamespace(id="cs_good", url="https://stripe.test/x"),
    )
    checkout = client.post(
        "/shop/checkout/stripe", json={"sku": "gems_small"}, headers=hdr,
    ).json()
    purchase_id = checkout["purchase_id"]

    # Before grant.
    before = client.get("/me", headers=hdr).json()

    # Simulate the webhook event.
    session_obj = SimpleNamespace(
        id="cs_good",
        metadata={"account_id": str(account_id), "sku": "gems_small", "purchase_id": str(purchase_id)},
    )
    event = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(object=session_obj),
    )
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda **_: event)

    r = client.post(
        "/shop/webhooks/stripe",
        content=b"{}", headers={"stripe-signature": "valid"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"received": True, "type": "checkout.session.completed"}

    # Currency granted, purchase marked COMPLETED.
    after = client.get("/me", headers=hdr).json()
    assert after["gems"] == before["gems"] + 300
    with SessionLocal() as db:
        p = db.get(Purchase, purchase_id)
        assert p.state == PurchaseState.COMPLETED
        # Ledger has one GRANT row.
        grants = db.query(PurchaseLedger).filter_by(
            purchase_id=purchase_id, direction=LedgerDirection.GRANT
        ).all()
        assert len(grants) == 1 and grants[0].kind == "gems" and grants[0].amount == 300

    # Second delivery of the same event must not double-grant.
    r = client.post(
        "/shop/webhooks/stripe",
        content=b"{}", headers={"stripe-signature": "valid"},
    )
    assert r.status_code == 200
    after2 = client.get("/me", headers=hdr).json()
    assert after2["gems"] == after["gems"], "duplicate webhook delivery double-granted"


def test_webhook_completed_unknown_session_is_no_op(client, configured_stripe, monkeypatch) -> None:
    """A completion event for a session we don't know about should be ignored, not crash."""
    session_obj = SimpleNamespace(id="cs_never_heard_of_it", metadata={})
    event = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(object=session_obj),
    )
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda **_: event)
    r = client.post(
        "/shop/webhooks/stripe",
        content=b"{}", headers={"stripe-signature": "valid"},
    )
    assert r.status_code == 200


def test_webhook_ignores_unsubscribed_events(client, configured_stripe, monkeypatch) -> None:
    """Unhandled event types are 200'd (we unsubscribe by not acting) so Stripe stops retrying."""
    event = SimpleNamespace(
        type="customer.created",
        data=SimpleNamespace(object=SimpleNamespace(id="cus_x")),
    )
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda **_: event)
    r = client.post(
        "/shop/webhooks/stripe",
        content=b"{}", headers={"stripe-signature": "valid"},
    )
    assert r.status_code == 200
    assert r.json()["type"] == "customer.created"
