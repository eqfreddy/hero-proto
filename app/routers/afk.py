"""AFK income loop endpoints.

GET  /afk         — pending pool snapshot (read-only, safe to poll)
POST /afk/claim   — bank pending coins/XP, reset accrual timer
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import afk as afk_service
from app.db import get_db
from app.deps import get_current_account
from app.models import Account

router = APIRouter(prefix="/afk", tags=["afk"])


@router.get("")
def get_status(
    account: Annotated[Account, Depends(get_current_account)],
) -> dict:
    return afk_service.pending(account)


@router.post("/claim")
def claim(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    granted = afk_service.claim(db, account)
    db.commit()
    return granted
