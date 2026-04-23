"""Store primitives: product catalog grant/refund helpers + idempotent purchase creation.

Kept separate from routers so admin tools and scheduled worker jobs can reuse.
Never call these from anywhere but the store router and admin router — they write
to both the account balance and the audit ledger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    HeroInstance,
    HeroTemplate,
    LedgerDirection,
    Purchase,
    PurchaseLedger,
    PurchaseState,
    ShopProduct,
    utcnow,
)

# Kinds understood in a product's contents_json. Keep the list explicit so a malformed
# product (typo in kind) doesn't silently grant nothing — we fail loudly instead.
GRANTABLE_CURRENCIES = ("gems", "shards", "coins", "access_cards")


@dataclass
class GrantSummary:
    currencies: dict[str, int]
    hero_instance_id: int | None


def product_contents(product: ShopProduct) -> dict:
    try:
        data = json.loads(product.contents_json or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        return {}
    return data


def apply_grant(db: Session, account: Account, purchase: Purchase, contents: dict) -> GrantSummary:
    """Add contents to the account and write ledger entries. No commit — caller commits."""
    granted: dict[str, int] = {}
    for kind in GRANTABLE_CURRENCIES:
        amount = int(contents.get(kind, 0) or 0)
        if amount <= 0:
            continue
        setattr(account, kind, getattr(account, kind) + amount)
        db.add(PurchaseLedger(
            purchase_id=purchase.id, kind=kind, amount=amount,
            direction=LedgerDirection.GRANT,
        ))
        granted[kind] = amount

    hero_instance_id: int | None = None
    code = contents.get("hero_template_code")
    if code:
        tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
        if tmpl is None:
            raise ValueError(f"product references missing hero template {code!r}")
        hero = HeroInstance(account_id=account.id, template_id=tmpl.id)
        db.add(hero)
        db.flush()
        hero_instance_id = hero.id
        db.add(PurchaseLedger(
            purchase_id=purchase.id, kind="hero", amount=hero.id,
            direction=LedgerDirection.GRANT, note=f"template={code}",
        ))
    return GrantSummary(currencies=granted, hero_instance_id=hero_instance_id)


def apply_refund(db: Session, account: Account, purchase: Purchase, reason: str = "") -> dict[str, int]:
    """Reverse grants recorded in the ledger and mark purchase REFUNDED. No commit."""
    if purchase.state == PurchaseState.REFUNDED:
        return {}
    reversed_: dict[str, int] = {}
    grants = list(
        db.scalars(
            select(PurchaseLedger).where(
                PurchaseLedger.purchase_id == purchase.id,
                PurchaseLedger.direction == LedgerDirection.GRANT,
            )
        )
    )
    for g in grants:
        if g.kind in GRANTABLE_CURRENCIES:
            cur = getattr(account, g.kind, 0)
            # Clamp to zero — refund should never push a balance negative; if the player
            # already spent down the paid currency, the clawback eats what's left.
            new_value = max(0, cur - g.amount)
            clawback = cur - new_value
            setattr(account, g.kind, new_value)
            db.add(PurchaseLedger(
                purchase_id=purchase.id, kind=g.kind, amount=clawback,
                direction=LedgerDirection.REFUND,
                note=f"original grant {g.amount}, clawed {clawback}",
            ))
            reversed_[g.kind] = clawback
        elif g.kind == "hero":
            # Hero clawbacks are typically a bad-UX move; log only. Could delete the hero
            # but players might have levelled / geared it. CS call, not automatic.
            db.add(PurchaseLedger(
                purchase_id=purchase.id, kind="hero", amount=g.amount,
                direction=LedgerDirection.REFUND,
                note="not clawed — manual CS decision",
            ))

    purchase.state = PurchaseState.REFUNDED
    purchase.refunded_at = utcnow()
    purchase.refund_reason = (reason or "").strip()[:256]
    return reversed_


def count_account_purchases(db: Session, account_id: int, sku: str) -> int:
    from sqlalchemy import func
    return db.scalar(
        select(func.count(Purchase.id)).where(
            Purchase.account_id == account_id,
            Purchase.sku == sku,
            Purchase.state.in_((PurchaseState.COMPLETED, PurchaseState.PENDING)),
        )
    ) or 0
