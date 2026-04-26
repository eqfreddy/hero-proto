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
GRANTABLE_CURRENCIES = ("gems", "shards", "coins", "access_cards", "free_summon_credits")


# Phase 2.4 — known QoL unlocks. Catalog as data so a typo in a product's
# contents_json fails loudly. Each entry: code → human-readable label +
# optional side-effect (e.g. extra_team_presets bumps a soft cap).
KNOWN_QOL_UNLOCKS: dict[str, dict] = {
    # Skip-to-result button on /battles. Free accounts get the standard
    # simulate-and-watch path; this unlock collapses that into a single
    # POST that also auto-submits the team. Pure QoL, no power impact.
    "auto_battle": {"label": "Auto-Battle", "kind": "flag"},
    # Bumps the team-preset cap from 5 to 10. Cap is enforced in the
    # team-presets router; the unlock just toggles a different ceiling.
    "extra_team_presets": {"label": "Extra Preset Slots (5→10)", "kind": "flag"},
    # Roster sort/filter options beyond the default rarity/power sort.
    "roster_sort_advanced": {"label": "Advanced Roster Sort", "kind": "flag"},
    # Quick-summon — skip the per-pull animation on x10. Cosmetic.
    "quick_summon": {"label": "Quick Summon", "kind": "flag"},
}


# Cosmetic frame catalog. Codes only; rendering happens client-side.
KNOWN_COSMETIC_FRAMES: set[str] = {
    "frame_neon_cubicle", "frame_terminal_green",
    "frame_legacy_brass", "frame_corp_platinum",
}


@dataclass
class GrantSummary:
    currencies: dict[str, int]
    hero_instance_id: int | None
    qol_unlocks: list[str]
    cosmetic_frames: list[str]
    extra_hero_slots: int
    extra_gear_slots: int


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

    # Phase 2.4 — QoL unlocks. Stored as JSON dict {code: granted_at_iso}.
    # Idempotent: re-granting an already-owned unlock is a no-op (mobile
    # restore-purchases hits this all the time).
    qol_granted: list[str] = []
    qol_codes = contents.get("qol_unlocks") or []
    if isinstance(qol_codes, str):
        qol_codes = [qol_codes]
    if qol_codes:
        try:
            owned = json.loads(account.qol_unlocks_json or "{}")
            if not isinstance(owned, dict):
                owned = {}
        except json.JSONDecodeError:
            owned = {}
        for unlock in qol_codes:
            unlock = str(unlock)
            if unlock not in KNOWN_QOL_UNLOCKS:
                raise ValueError(f"product references unknown QoL unlock {unlock!r}")
            if unlock in owned:
                # Already owned — restore-purchases path. Note in ledger so
                # CS can audit, but don't double-log a fresh grant.
                db.add(PurchaseLedger(
                    purchase_id=purchase.id, kind=f"qol:{unlock}", amount=0,
                    direction=LedgerDirection.GRANT, note="restore (already owned)",
                ))
                continue
            owned[unlock] = utcnow().isoformat()
            qol_granted.append(unlock)
            db.add(PurchaseLedger(
                purchase_id=purchase.id, kind=f"qol:{unlock}", amount=1,
                direction=LedgerDirection.GRANT,
            ))
        account.qol_unlocks_json = json.dumps(owned, separators=(",", ":"))

    # Cosmetic frames. JSON list of frame codes. Same idempotent shape.
    cosm_granted: list[str] = []
    cosm_codes = contents.get("cosmetic_frames") or []
    if isinstance(cosm_codes, str):
        cosm_codes = [cosm_codes]
    if cosm_codes:
        try:
            owned_frames = json.loads(account.cosmetic_frames_json or "[]")
            if not isinstance(owned_frames, list):
                owned_frames = []
        except json.JSONDecodeError:
            owned_frames = []
        owned_set = set(owned_frames)
        for frame in cosm_codes:
            frame = str(frame)
            if frame not in KNOWN_COSMETIC_FRAMES:
                raise ValueError(f"product references unknown cosmetic frame {frame!r}")
            if frame in owned_set:
                db.add(PurchaseLedger(
                    purchase_id=purchase.id, kind=f"frame:{frame}", amount=0,
                    direction=LedgerDirection.GRANT, note="restore (already owned)",
                ))
                continue
            owned_frames.append(frame)
            owned_set.add(frame)
            cosm_granted.append(frame)
            db.add(PurchaseLedger(
                purchase_id=purchase.id, kind=f"frame:{frame}", amount=1,
                direction=LedgerDirection.GRANT,
            ))
        account.cosmetic_frames_json = json.dumps(owned_frames, separators=(",", ":"))

    # Extra hero / gear slot bumps — additive on the cap. Always granted
    # cleanly (no idempotency: a player buying the slot-pack twice gets
    # 2× the slots).
    extra_hero = int(contents.get("extra_hero_slots", 0) or 0)
    extra_gear = int(contents.get("extra_gear_slots", 0) or 0)
    if extra_hero > 0:
        account.hero_slot_cap = (account.hero_slot_cap or 0) + extra_hero
        db.add(PurchaseLedger(
            purchase_id=purchase.id, kind="extra_hero_slots", amount=extra_hero,
            direction=LedgerDirection.GRANT,
        ))
    if extra_gear > 0:
        account.gear_slot_cap = (account.gear_slot_cap or 0) + extra_gear
        db.add(PurchaseLedger(
            purchase_id=purchase.id, kind="extra_gear_slots", amount=extra_gear,
            direction=LedgerDirection.GRANT,
        ))

    return GrantSummary(
        currencies=granted, hero_instance_id=hero_instance_id,
        qol_unlocks=qol_granted, cosmetic_frames=cosm_granted,
        extra_hero_slots=extra_hero, extra_gear_slots=extra_gear,
    )


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
        elif g.kind.startswith("qol:") and g.amount > 0:
            # Phase 2.4 — IAP refund must reverse the QoL unlock so a
            # chargeback doesn't leak the auto-battle / preset-slots flag.
            # `amount=0` ledger rows are the restore-purchases path; skip.
            unlock = g.kind.split(":", 1)[1]
            try:
                owned = json.loads(account.qol_unlocks_json or "{}")
                if isinstance(owned, dict) and unlock in owned:
                    del owned[unlock]
                    account.qol_unlocks_json = json.dumps(owned, separators=(",", ":"))
                    reversed_[g.kind] = 1
                    db.add(PurchaseLedger(
                        purchase_id=purchase.id, kind=g.kind, amount=1,
                        direction=LedgerDirection.REFUND,
                        note=f"unlock {unlock!r} revoked",
                    ))
            except json.JSONDecodeError:
                pass
        elif g.kind.startswith("frame:") and g.amount > 0:
            frame = g.kind.split(":", 1)[1]
            try:
                owned_frames = json.loads(account.cosmetic_frames_json or "[]")
                if isinstance(owned_frames, list) and frame in owned_frames:
                    owned_frames = [f for f in owned_frames if f != frame]
                    account.cosmetic_frames_json = json.dumps(owned_frames, separators=(",", ":"))
                    reversed_[g.kind] = 1
                    db.add(PurchaseLedger(
                        purchase_id=purchase.id, kind=g.kind, amount=1,
                        direction=LedgerDirection.REFUND,
                        note=f"frame {frame!r} revoked",
                    ))
            except json.JSONDecodeError:
                pass
        elif g.kind == "extra_hero_slots":
            # Slot-cap refunds are clamped: never push the cap below 50
            # (the seeded default) so the clawback can't wedge a player
            # whose roster grew past the original ceiling.
            new_cap = max(50, (account.hero_slot_cap or 50) - g.amount)
            clawed = (account.hero_slot_cap or 50) - new_cap
            account.hero_slot_cap = new_cap
            reversed_[g.kind] = clawed
            db.add(PurchaseLedger(
                purchase_id=purchase.id, kind=g.kind, amount=clawed,
                direction=LedgerDirection.REFUND,
                note=f"slots clawed {clawed} (floor 50)",
            ))
        elif g.kind == "extra_gear_slots":
            new_cap = max(200, (account.gear_slot_cap or 200) - g.amount)
            clawed = (account.gear_slot_cap or 200) - new_cap
            account.gear_slot_cap = new_cap
            reversed_[g.kind] = clawed
            db.add(PurchaseLedger(
                purchase_id=purchase.id, kind=g.kind, amount=clawed,
                direction=LedgerDirection.REFUND,
                note=f"gear slots clawed {clawed} (floor 200)",
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
