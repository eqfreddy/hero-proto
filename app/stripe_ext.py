"""Stripe integration bolted onto the shop router.

Extracted to its own module so the heavy Stripe-specific imports and the
webhook-event dispatch don't clutter shop.py. Only imported lazily from the
router, so tests that don't exercise Stripe don't need the SDK configured.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.models import (
    Account,
    Purchase,
    PurchaseState,
    ShopProduct,
    utcnow,
)
from app.store import apply_grant, apply_refund, count_account_purchases, product_contents

log = logging.getLogger("shop.stripe")

router = APIRouter(prefix="/shop", tags=["shop-stripe"])


class StripeCheckoutIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    client_ref: str | None = Field(default=None, max_length=128)


class StripeCheckoutOut(BaseModel):
    checkout_url: str
    session_id: str
    purchase_id: int


def _require_stripe_configured() -> None:
    if not settings.stripe_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stripe is not configured — set HEROPROTO_STRIPE_API_KEY",
        )
    stripe.api_key = settings.stripe_api_key


def _time_active(product: ShopProduct, now) -> bool:
    if not product.is_active:
        return False
    if product.starts_at is not None and now < product.starts_at:
        return False
    if product.ends_at is not None and now >= product.ends_at:
        return False
    return True


@router.post(
    "/checkout/stripe",
    response_model=StripeCheckoutOut,
    status_code=status.HTTP_201_CREATED,
)
def create_stripe_checkout(
    body: StripeCheckoutIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> StripeCheckoutOut:
    """Create a Stripe Checkout Session and return the hosted URL.

    Flow:
      1. Client POSTs here, gets checkout_url.
      2. Client navigates to that URL (Stripe-hosted payment page).
      3. On success, Stripe redirects to HEROPROTO_STRIPE_SUCCESS_URL and fires
         the `checkout.session.completed` webhook at /shop/webhooks/stripe.
      4. Webhook completes the pre-created Purchase and grants contents.
    """
    _require_stripe_configured()

    product = db.scalar(select(ShopProduct).where(ShopProduct.sku == body.sku))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no product {body.sku!r}")
    if not product.stripe_price_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"product {body.sku} has no Stripe price configured",
        )

    now = utcnow()
    if not _time_active(product, now):
        raise HTTPException(status.HTTP_409_CONFLICT, "product is not currently available")
    if product.per_account_limit:
        owned = count_account_purchases(db, account.id, product.sku)
        if owned >= product.per_account_limit:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"per-account purchase limit of {product.per_account_limit} reached",
            )

    client_ref = body.client_ref or uuid.uuid4().hex

    contents = product_contents(product)
    purchase = Purchase(
        account_id=account.id,
        sku=product.sku,
        title_snapshot=product.title,
        price_cents_paid=product.price_cents,
        currency_code=product.currency_code,
        processor="stripe",
        processor_ref=f"pending:{client_ref}",
        state=PurchaseState.PENDING,
        contents_snapshot_json=json.dumps(contents),
    )
    db.add(purchase)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"a pending Stripe checkout already exists for client_ref {client_ref!r}",
        ) from None

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": product.stripe_price_id, "quantity": 1}],
            success_url=settings.stripe_success_url,
            cancel_url=settings.stripe_cancel_url,
            client_reference_id=client_ref,
            metadata={
                "account_id": str(account.id),
                "sku": product.sku,
                "purchase_id": str(purchase.id),
                "client_ref": client_ref,
            },
        )
    except stripe.error.StripeError as exc:
        db.delete(purchase)
        db.commit()
        log.exception("stripe session create failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}") from exc

    purchase.processor_ref = session.id
    db.commit()
    db.refresh(purchase)

    return StripeCheckoutOut(
        checkout_url=session.url,
        session_id=session.id,
        purchase_id=purchase.id,
    )


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Stripe webhook receiver. Verifies signature before doing any work."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stripe webhook secret not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid payload: {exc}") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "invalid Stripe signature — event rejected",
        ) from exc

    event_type = event["type"] if isinstance(event, dict) else event.type
    data_object = event["data"]["object"] if isinstance(event, dict) else event.data.object

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data_object)
    elif event_type == "charge.refunded":
        _handle_charge_refunded(db, data_object)
    else:
        log.info("stripe webhook: ignoring event type %s", event_type)

    return {"received": True, "type": event_type}


def _get(obj, key: str):
    """Access either a Stripe object attribute or a dict key."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _handle_checkout_completed(db: Session, session) -> None:
    """Mark the pre-created Purchase row COMPLETED and apply grant."""
    session_id = _get(session, "id")
    if not session_id:
        log.warning("stripe checkout.session.completed without id")
        return

    purchase = db.scalar(
        select(Purchase).where(
            Purchase.processor == "stripe",
            Purchase.processor_ref == session_id,
        )
    )
    if purchase is None:
        # Fallback: locate via metadata.purchase_id.
        metadata = _get(session, "metadata") or {}
        pid_raw = metadata.get("purchase_id") if isinstance(metadata, dict) else _get(metadata, "purchase_id")
        try:
            pid = int(pid_raw) if pid_raw else None
        except (TypeError, ValueError):
            pid = None
        if pid is not None:
            purchase = db.get(Purchase, pid)
        if purchase is None:
            log.warning(
                "stripe checkout.session.completed: no matching Purchase for session %s",
                session_id,
            )
            return

    if purchase.state == PurchaseState.COMPLETED:
        log.info("stripe webhook: purchase %s already completed — idempotent no-op", purchase.id)
        return
    if purchase.state == PurchaseState.REFUNDED:
        log.warning(
            "stripe webhook: received completion for already-refunded purchase %s", purchase.id
        )
        return

    account = db.get(Account, purchase.account_id)
    if account is None:
        log.error("stripe webhook: purchase %s references missing account", purchase.id)
        return

    try:
        contents = json.loads(purchase.contents_snapshot_json or "{}")
    except json.JSONDecodeError:
        contents = {}
    try:
        apply_grant(db, account, purchase, contents)
    except ValueError as exc:
        purchase.state = PurchaseState.FAILED
        purchase.refund_reason = str(exc)[:256]
        db.commit()
        log.exception("stripe webhook: apply_grant failed for purchase %s", purchase.id)
        return

    purchase.state = PurchaseState.COMPLETED
    purchase.completed_at = utcnow()
    purchase.processor_ref = session_id
    db.commit()
    log.info(
        "stripe webhook: purchase %s completed (account=%s sku=%s)",
        purchase.id, purchase.account_id, purchase.sku,
    )


def _handle_charge_refunded(db: Session, charge) -> None:
    """Chargeback path: reverse any completed purchase tied to this charge's session."""
    payment_intent = _get(charge, "payment_intent")
    if not payment_intent:
        log.warning("stripe webhook: charge.refunded without payment_intent")
        return

    try:
        stripe.api_key = settings.stripe_api_key
        sessions = stripe.checkout.Session.list(payment_intent=payment_intent, limit=1)
    except stripe.error.StripeError:
        log.exception("stripe webhook: failed to resolve session for pi %s", payment_intent)
        return

    sessions_data = sessions.data if hasattr(sessions, "data") else sessions.get("data", [])
    if not sessions_data:
        log.warning("stripe webhook: no session for pi %s", payment_intent)
        return
    session_id = sessions_data[0].id if hasattr(sessions_data[0], "id") else sessions_data[0]["id"]

    purchase = db.scalar(
        select(Purchase).where(
            Purchase.processor == "stripe",
            Purchase.processor_ref == session_id,
        )
    )
    if purchase is None or purchase.state != PurchaseState.COMPLETED:
        log.info(
            "stripe webhook: no completed purchase to refund for session %s", session_id
        )
        return

    account = db.get(Account, purchase.account_id)
    if account is None:
        log.error("stripe webhook: refund on purchase %s with missing account", purchase.id)
        return

    apply_refund(db, account, purchase, reason=f"stripe chargeback: {_get(charge, 'id') or ''}")
    db.commit()
    log.info("stripe webhook: refunded purchase %s via chargeback", purchase.id)
