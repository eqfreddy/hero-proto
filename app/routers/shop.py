"""In-game store endpoints.

Product catalog is read-only from the client. Purchases go through a processor
abstraction — today only "mock" is wired (dev/alpha); real Stripe / Apple /
Google webhooks will call the same `_complete_purchase` codepath with their own
signed receipts.

Idempotency: every completed sale is keyed on (processor, processor_ref). A
duplicate webhook (same charge id) finds the existing Purchase row and no-ops
instead of double-granting.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.store import apply_grant, count_account_purchases, product_contents

router = APIRouter(prefix="/shop", tags=["shop"])


# --- schemas -----------------------------------------------------------------


class ProductOut(BaseModel):
    sku: str
    title: str
    description: str
    kind: str
    price_cents: int
    currency_code: str
    contents: dict
    per_account_limit: int
    owned_count: int
    available: bool
    unavailable_reason: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class PurchaseIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    # Idempotency token from the client — lets a retried network request dedupe to
    # the same Purchase row. Optional — server synthesizes one per call if absent.
    client_ref: str | None = Field(default=None, max_length=128)


class PurchaseOut(BaseModel):
    id: int
    sku: str
    state: str
    price_cents_paid: int
    currency_code: str
    granted: dict
    processor: str
    processor_ref: str
    created_at: datetime
    completed_at: datetime | None
    refunded_at: datetime | None


# --- helpers -----------------------------------------------------------------


def _time_active(product: ShopProduct, now: datetime) -> bool:
    if not product.is_active:
        return False
    if product.starts_at is not None and now < product.starts_at:
        return False
    if product.ends_at is not None and now >= product.ends_at:
        return False
    return True


def _product_out(db: Session, product: ShopProduct, owned: int, now: datetime) -> ProductOut:
    reason: str | None = None
    active = _time_active(product, now)
    if not product.is_active:
        reason = "inactive"
    elif product.starts_at is not None and now < product.starts_at:
        reason = "not started yet"
    elif product.ends_at is not None and now >= product.ends_at:
        reason = "ended"
    elif product.per_account_limit and owned >= product.per_account_limit:
        reason = "already purchased"
        active = False
    return ProductOut(
        sku=product.sku,
        title=product.title,
        description=product.description,
        kind=str(product.kind),
        price_cents=product.price_cents,
        currency_code=product.currency_code,
        contents=product_contents(product),
        per_account_limit=product.per_account_limit,
        owned_count=owned,
        available=active,
        unavailable_reason=reason,
        starts_at=product.starts_at,
        ends_at=product.ends_at,
    )


def _purchase_out(p: Purchase) -> PurchaseOut:
    try:
        granted = json.loads(p.contents_snapshot_json or "{}")
    except json.JSONDecodeError:
        granted = {}
    return PurchaseOut(
        id=p.id, sku=p.sku, state=str(p.state),
        price_cents_paid=p.price_cents_paid, currency_code=p.currency_code,
        granted=granted, processor=p.processor, processor_ref=p.processor_ref,
        created_at=p.created_at, completed_at=p.completed_at, refunded_at=p.refunded_at,
    )


# --- endpoints ---------------------------------------------------------------


@router.get("/products", response_model=list[ProductOut])
def list_products(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    include_unavailable: bool = False,
) -> list[ProductOut]:
    now = utcnow()
    rows = list(
        db.scalars(
            select(ShopProduct)
            .order_by(ShopProduct.sort_order, ShopProduct.id)
        )
    )
    out: list[ProductOut] = []
    for p in rows:
        owned = count_account_purchases(db, account.id, p.sku) if p.per_account_limit else 0
        po = _product_out(db, p, owned, now)
        if not po.available and not include_unavailable:
            continue
        out.append(po)
    return out


@router.post("/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    body: PurchaseIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOut:
    """Mock-payment purchase.

    Real processors will use their own webhook endpoints; this one just grants
    immediately. Gated on `HEROPROTO_MOCK_PAYMENTS_ENABLED=1` so prod accidents
    can't happen.
    """
    if not settings.mock_payments_enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "mock payments are disabled — set HEROPROTO_MOCK_PAYMENTS_ENABLED=1 in dev "
            "or use a real processor endpoint",
        )

    product = db.scalar(select(ShopProduct).where(ShopProduct.sku == body.sku))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no product {body.sku!r}")

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

    processor_ref = (body.client_ref or uuid.uuid4().hex)
    # Idempotency: same (processor, processor_ref) yields the existing purchase.
    existing = db.scalar(
        select(Purchase).where(
            Purchase.processor == "mock",
            Purchase.processor_ref == processor_ref,
        )
    )
    if existing is not None:
        if existing.account_id != account.id:
            # A ref collision across accounts — treat as a 409; never reveal the other account.
            raise HTTPException(status.HTTP_409_CONFLICT, "duplicate purchase reference")
        return _purchase_out(existing)

    contents = product_contents(product)
    purchase = Purchase(
        account_id=account.id,
        sku=product.sku,
        title_snapshot=product.title,
        price_cents_paid=product.price_cents,
        currency_code=product.currency_code,
        processor="mock",
        processor_ref=processor_ref,
        state=PurchaseState.PENDING,
        contents_snapshot_json=json.dumps(contents),
    )
    db.add(purchase)
    try:
        db.flush()
    except IntegrityError:
        # Race: another request inserted the same processor_ref between our check and flush.
        db.rollback()
        existing = db.scalar(
            select(Purchase).where(
                Purchase.processor == "mock",
                Purchase.processor_ref == processor_ref,
            )
        )
        if existing is not None and existing.account_id == account.id:
            return _purchase_out(existing)
        raise HTTPException(status.HTTP_409_CONFLICT, "duplicate purchase reference") from None

    try:
        apply_grant(db, account, purchase, contents)
    except ValueError as exc:
        purchase.state = PurchaseState.FAILED
        purchase.refund_reason = str(exc)[:256]
        db.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    purchase.state = PurchaseState.COMPLETED
    purchase.completed_at = utcnow()
    db.commit()
    db.refresh(purchase)
    return _purchase_out(purchase)


# --- IAP receipt verification (Apple StoreKit + Google Play Billing) ---
#
# The mobile clients (Capacitor wrapping the PWA) POST signed receipts here
# after the platform-native payment flow completes. We verify with Apple /
# Google, look up the matching ShopProduct, and grant — same idempotency
# pattern as the mock endpoint above (one Purchase per processor_ref).


class ReceiptIn(BaseModel):
    """Mobile-client payload after a successful native IAP."""
    sku: str
    receipt: str   # opaque blob — signed JWS for Apple, JSON for Google


def _complete_iap(
    db: Session, account: Account, processor: str, body: ReceiptIn,
) -> Purchase:
    """Common path for /shop/iap/{apple,google}. Verifies receipt, idempotent
    by (processor, processor_ref), grants contents, returns the Purchase."""
    from app.payment_adapters import ReceiptError, get_adapter

    try:
        adapter = get_adapter(processor)
        verified = adapter.verify(body.receipt, claimed_sku=body.sku)
    except ReceiptError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    product = db.scalar(select(ShopProduct).where(ShopProduct.sku == verified.sku))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no product {verified.sku!r}")

    # Idempotency: same (processor, processor_ref) returns the existing row.
    existing = db.scalar(
        select(Purchase).where(
            Purchase.processor == verified.processor,
            Purchase.processor_ref == verified.processor_ref,
        )
    )
    if existing is not None:
        if existing.account_id != account.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "duplicate purchase reference")
        return existing

    contents = product_contents(product)
    purchase = Purchase(
        account_id=account.id,
        sku=product.sku,
        title_snapshot=product.title,
        price_cents_paid=product.price_cents,
        currency_code=product.currency_code,
        processor=verified.processor,
        processor_ref=verified.processor_ref,
        state=PurchaseState.PENDING,
        contents_snapshot_json=json.dumps(contents),
    )
    db.add(purchase)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Purchase).where(
                Purchase.processor == verified.processor,
                Purchase.processor_ref == verified.processor_ref,
            )
        )
        if existing is not None and existing.account_id == account.id:
            return existing
        raise HTTPException(status.HTTP_409_CONFLICT, "duplicate purchase reference") from None

    try:
        apply_grant(db, account, purchase, contents)
    except ValueError as exc:
        purchase.state = PurchaseState.FAILED
        purchase.refund_reason = str(exc)[:256]
        db.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    purchase.state = PurchaseState.COMPLETED
    purchase.completed_at = utcnow()
    db.commit()
    db.refresh(purchase)
    return purchase


@router.post("/iap/apple", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def iap_apple(
    body: ReceiptIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOut:
    """Apple StoreKit 2 receipt verification + grant."""
    return _purchase_out(_complete_iap(db, account, "apple", body))


@router.post("/iap/google", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def iap_google(
    body: ReceiptIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOut:
    """Google Play Billing receipt verification + grant."""
    return _purchase_out(_complete_iap(db, account, "google", body))


@router.get("/purchases/mine", response_model=list[PurchaseOut])
def list_my_purchases(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[PurchaseOut]:
    limit = max(1, min(200, limit))
    rows = db.scalars(
        select(Purchase)
        .where(Purchase.account_id == account.id)
        .order_by(Purchase.id.desc())
        .limit(limit)
    )
    return [_purchase_out(p) for p in rows]


# --- Shard store (in-game gems → shards exchange) ---------------------------
#
# A second monetization-adjacent path: rather than buying shards with real
# money (the existing shards_pack SKU), players can spend the gems they
# already have. Rate is fixed in settings. Daily cap stops one whale account
# from converting infinite gems → shards in a single sitting.


class ShardExchangeStatusOut(BaseModel):
    gems_per_batch: int
    shards_per_batch: int
    max_per_day: int
    used_today: int
    remaining_today: int


class ShardExchangeIn(BaseModel):
    batches: int = Field(ge=1, le=20, default=1)


class ShardExchangeOut(BaseModel):
    batches: int
    gems_spent: int
    shards_gained: int
    gems: int
    shards: int
    used_today: int
    remaining_today: int


def _today_key() -> str:
    return utcnow().strftime("%Y-%m-%d")


@router.get("/shard-exchange", response_model=ShardExchangeStatusOut)
def shard_exchange_status(
    account: Annotated[Account, Depends(get_current_account)],
) -> ShardExchangeStatusOut:
    """Caller's remaining daily exchange budget + the configured rate."""
    today = _today_key()
    used = account.shard_exchanges_today_count if account.shard_exchanges_today_key == today else 0
    return ShardExchangeStatusOut(
        gems_per_batch=settings.shard_exchange_gems_per_batch,
        shards_per_batch=settings.shard_exchange_shards_per_batch,
        max_per_day=settings.shard_exchange_max_per_day,
        used_today=used,
        remaining_today=max(0, settings.shard_exchange_max_per_day - used),
    )


@router.post("/shard-exchange", response_model=ShardExchangeOut, status_code=status.HTTP_201_CREATED)
def exchange_gems_for_shards(
    body: ShardExchangeIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> ShardExchangeOut:
    """Atomic gems → shards swap. Bounded by the per-day cap and the player's
    current gem balance. The whole `batches` count succeeds or fails — no
    partial credit if budget runs out mid-request.
    """
    today = _today_key()
    if account.shard_exchanges_today_key != today:
        account.shard_exchanges_today_key = today
        account.shard_exchanges_today_count = 0

    requested = body.batches
    remaining = settings.shard_exchange_max_per_day - account.shard_exchanges_today_count
    if remaining <= 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"daily shard-exchange limit reached ({settings.shard_exchange_max_per_day} batches)",
        )
    if requested > remaining:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"daily limit only allows {remaining} more batches today",
        )

    gems_cost = settings.shard_exchange_gems_per_batch * requested
    shards_gain = settings.shard_exchange_shards_per_batch * requested

    if account.gems < gems_cost:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough gems (need {gems_cost}, have {account.gems})",
        )

    account.gems -= gems_cost
    account.shards += shards_gain
    account.shard_exchanges_today_count += requested

    # Daily-quest hook — counts as gem spend.
    from app.daily import on_gems_spent
    on_gems_spent(db, account, gems_cost)

    db.commit()
    db.refresh(account)
    return ShardExchangeOut(
        batches=requested,
        gems_spent=gems_cost,
        shards_gained=shards_gain,
        gems=account.gems,
        shards=account.shards,
        used_today=account.shard_exchanges_today_count,
        remaining_today=max(0, settings.shard_exchange_max_per_day - account.shard_exchanges_today_count),
    )
