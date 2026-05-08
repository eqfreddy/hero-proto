"""Monthly Card subscription — daily gem drip for 30 days per purchase.

Design decisions (per gacha-research recommendations):
- $4.99 buys 30 days of card. Stacks: re-purchasing extends ends_at by N days.
- Daily drip: 50 gems/day, granted lazily when /me is called or on-demand
  via POST /monthly-card/claim. Idempotent via UTC-date lock.
- Instant grant on purchase: 100 gems immediately so the player feels value.
- Total: 100 + 50*30 = 1,600 gems for $4.99 — vs ~1,400 gems in the $19.99
  pack, the math screams 'best value' on the shop page (intentional).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Account, PurchaseLedger, LedgerDirection, utcnow

log = logging.getLogger(__name__)

CARD_DURATION_DAYS = 30
DAILY_DRIP_GEMS = 50
INSTANT_PURCHASE_GEMS = 100


def _today_utc_date() -> datetime:
    """Date-only timestamp for the current UTC day (00:00:00)."""
    now = utcnow()
    return datetime(now.year, now.month, now.day)


def is_active(account: Account) -> bool:
    if account.monthly_card_ends_at is None:
        return False
    return account.monthly_card_ends_at > utcnow()


def days_remaining(account: Account) -> int:
    if not is_active(account):
        return 0
    delta = account.monthly_card_ends_at - utcnow()
    return max(0, int(delta.total_seconds() // 86400) + (1 if delta.total_seconds() % 86400 > 0 else 0))


def can_claim_today(account: Account) -> bool:
    if not is_active(account):
        return False
    today = _today_utc_date()
    last = account.monthly_card_last_drip_at
    return last is None or last < today


def extend(account: Account, days: int = CARD_DURATION_DAYS) -> datetime:
    """Extend (or start) the card. Stacks if already active."""
    now = utcnow()
    base = account.monthly_card_ends_at if account.monthly_card_ends_at and account.monthly_card_ends_at > now else now
    new_end = base + timedelta(days=days)
    account.monthly_card_ends_at = new_end
    return new_end


def claim_daily_drip(db: Session, account: Account, *, purchase_id: int | None = None) -> int:
    """Grant the daily drip if eligible. Returns the gem count granted (0 if not eligible).
    Idempotent — second call same UTC day is a no-op."""
    if not can_claim_today(account):
        return 0
    account.gems = int(account.gems) + DAILY_DRIP_GEMS
    account.monthly_card_last_drip_at = _today_utc_date()
    if purchase_id is not None:
        db.add(PurchaseLedger(
            purchase_id=purchase_id, kind="gems", amount=DAILY_DRIP_GEMS,
            direction=LedgerDirection.GRANT, note="monthly card daily drip",
        ))
    return DAILY_DRIP_GEMS


def status(account: Account) -> dict:
    return {
        "active": is_active(account),
        "ends_at": account.monthly_card_ends_at.isoformat() if account.monthly_card_ends_at else None,
        "days_remaining": days_remaining(account),
        "drip_available_today": can_claim_today(account),
        "drip_gems_per_day": DAILY_DRIP_GEMS,
    }
