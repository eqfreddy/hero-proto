"""Monthly Card endpoints.

GET  /monthly-card           — status: active/days-remaining/drip-available
POST /monthly-card/claim     — claim today's drip if eligible (idempotent)
POST /monthly-card/purchase  — mock-fulfill (dev) OR Stripe checkout URL (prod)

Backed by the same shop SKU + apply_grant pipeline as Battle Pass premium —
this endpoint is the convenience wrapper.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import monthly_card as mc_service
from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.models import (
    Account, LedgerDirection, Purchase, PurchaseLedger, PurchaseState,
    ShopProduct, utcnow,
)

router = APIRouter(prefix="/monthly-card", tags=["monthly-card"])

MONTHLY_CARD_SKU = "monthly_card"


@router.get("")
def get_status(
    account: Annotated[Account, Depends(get_current_account)],
) -> dict:
    return mc_service.status(account)


@router.post("/claim")
def claim_today(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    granted = mc_service.claim_daily_drip(db, account)
    db.commit()
    return {
        "granted_gems": granted,
        "already_claimed": granted == 0 and mc_service.is_active(account),
        "card_active": mc_service.is_active(account),
    }


@router.post("/purchase", status_code=status.HTTP_201_CREATED)
def purchase_card(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Buy a Monthly Card. Mode auto-selected:
      - mock_payments_enabled → instant grant + audit row.
      - else → Stripe Checkout URL; webhook completes the Purchase and
        apply_grant extends the card."""
    product = db.scalar(select(ShopProduct).where(ShopProduct.sku == MONTHLY_CARD_SKU))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "monthly card product not seeded")

    if settings.mock_payments_enabled:
        # Mirror the shop mock-purchase shape.
        from app.store import apply_grant, product_contents
        contents = product_contents(product)
        p = Purchase(
            account_id=account.id,
            sku=product.sku,
            title_snapshot=product.title,
            price_cents_paid=product.price_cents,
            currency_code=product.currency_code,
            processor="mock",
            processor_ref=f"mc-mock-{account.id}-{utcnow().isoformat()}",
            state=PurchaseState.PENDING,
            contents_snapshot_json="{}",
        )
        db.add(p)
        db.flush()
        apply_grant(db, account, p, contents)
        p.state = PurchaseState.COMPLETED
        p.completed_at = utcnow()
        db.commit()
        return {
            "purchased": True,
            "mode": "mock",
            "ends_at": account.monthly_card_ends_at.isoformat() if account.monthly_card_ends_at else None,
            "purchase_id": p.id,
            "checkout_url": None,
        }

    from app.stripe_ext import create_stripe_checkout, StripeCheckoutIn
    out = create_stripe_checkout(StripeCheckoutIn(sku=product.sku), account=account, db=db)
    return {
        "purchased": False,
        "mode": "stripe",
        "ends_at": account.monthly_card_ends_at.isoformat() if account.monthly_card_ends_at else None,
        "checkout_url": out.checkout_url,
        "purchase_id": out.purchase_id,
    }
