"""Battle Pass endpoints.

GET  /battle-pass                  — active season + progress + reward tracks
POST /battle-pass/claim/{tier}     — body: {"track": "free"|"premium"}, grants tier rewards
POST /battle-pass/purchase-premium — buy premium track for active season ($9.99 default)

Premium purchase uses the existing `/shop` Stripe path via SKU
`battle_pass_premium_<season_code>`. This router exposes a convenience
endpoint that mock-fulfills in dev/test envs and otherwise delegates to
shop.purchase().
"""
from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import battle_pass as bp_service
from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, LedgerDirection, Purchase, PurchaseLedger, PurchaseState, utcnow

router = APIRouter(prefix="/battle-pass", tags=["battle-pass"])
log = logging.getLogger(__name__)


class ClaimIn(BaseModel):
    track: Literal["free", "premium"]


@router.get("")
def get_battle_pass(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return bp_service.state_for_account(db, account)


@router.post("/claim/{tier}")
def claim_tier(
    tier: int,
    body: ClaimIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        result = bp_service.claim_tier(db, account, tier, track=body.track)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    db.commit()
    return result


@router.post("/purchase-premium", status_code=status.HTTP_201_CREATED)
def purchase_premium(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Mock-fulfilled premium-track purchase for the active season.

    Real money flow: client calls /shop/purchase with SKU
    `battle_pass_premium_<season_code>`; the shop fulfillment path calls
    bp_service.grant_premium. This endpoint is the dev/QA shortcut and the
    fallback when mock payments are enabled.
    """
    season = bp_service.active_season(db)
    if season is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no active battle pass season")

    if not settings.mock_payments_enabled:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "use /shop/purchase with the battle-pass SKU when mock payments are off",
        )

    bp = bp_service.grant_premium(db, account, season)
    # Audit row so this still surfaces in /me/purchases.
    p = Purchase(
        account_id=account.id,
        sku=f"battle_pass_premium_{season.code}",
        title_snapshot=f"{season.name} — Premium Pass",
        price_cents_paid=season.premium_price_cents,
        currency_code="USD",
        processor="mock",
        processor_ref=f"bp-mock-{account.id}-{season.id}",
        state=PurchaseState.COMPLETED,
        contents_snapshot_json="{}",
        completed_at=utcnow(),
    )
    db.add(p)
    db.flush()
    db.add(PurchaseLedger(
        purchase_id=p.id, kind="battle_pass", amount=1, direction=LedgerDirection.GRANT,
        note=f"Premium pass for {season.code}",
    ))
    db.commit()
    return {
        "purchased": True,
        "season_code": season.code,
        "premium_purchased_at": bp.premium_purchased_at.isoformat() if bp.premium_purchased_at else None,
        "purchase_id": p.id,
    }
