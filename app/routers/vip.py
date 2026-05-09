"""VIP tier endpoints.

GET  /vip          — current level + perks + next-tier preview
POST /vip/claim    — bank today's VIP gem drip if eligible (idempotent UTC-day)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import vip as vip_service
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, PurchaseLedger, LedgerDirection

router = APIRouter(prefix="/vip", tags=["vip"])


@router.get("")
def get_status(
    account: Annotated[Account, Depends(get_current_account)],
) -> dict:
    return vip_service.status(account)


@router.post("/claim")
def claim_drip(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    granted = vip_service.claim_daily_drip(account)
    db.commit()
    return {
        "granted_gems": granted,
        "already_claimed": granted == 0 and not vip_service._drip_available(account),
    }
