"""Crafting catalog: materials and recipes.

Content-as-code: keep balance edits + new recipes in this file rather than a
DB-driven editor. New material? Add a row. New recipe? Add a row. Run tests.

Materials drop from battles + raids via `roll_material_drops()`. Recipes
exchange materials (and optionally currency) for stuff: gear, currency,
free summon credits, even heroes for special event recipes.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, CraftLog, CraftMaterial, HeroInstance, HeroTemplate


# --- Catalog -----------------------------------------------------------------


@dataclass(frozen=True)
class Material:
    code: str
    name: str
    rarity: str        # cosmetic only — drives card border color in UI
    description: str
    icon: str = "📦"   # emoji shown in UI


@dataclass(frozen=True)
class MaterialDrop:
    material_code: str
    chance: float       # 0..1
    qty_min: int = 1
    qty_max: int = 1


@dataclass(frozen=True)
class Recipe:
    code: str
    name: str
    description: str
    materials: dict[str, int]            # code -> qty consumed
    coin_cost: int = 0
    gem_cost: int = 0
    output: dict = field(default_factory=dict)  # {gems, shards, coins, access_cards, free_summon_credits, hero_template_code}
    icon: str = "⚒️"


# Six materials covering the rarity spectrum. The names lean into the
# corporate-IT theme so even the inventory tab feels on-brand.
MATERIALS: dict[str, Material] = {m.code: m for m in [
    Material("rusted_keyboard_key", "Rusted Keyboard Key", "COMMON",
             "Worn from a thousand 'Have you tried turning it off?'.", "⌨️"),
    Material("expired_certificate", "Expired Certificate", "COMMON",
             "TLS handshake failed three quarters ago.", "📜"),
    Material("legacy_punch_card", "Legacy Punch Card", "UNCOMMON",
             "Mainframe artifact. Smells faintly of carbon.", "🃏"),
    Material("on_call_token", "On-Call Token", "RARE",
             "A page that wasn't escalated. Vibrates ominously.", "📟"),
    Material("ceo_signature", "CEO Signature", "EPIC",
             "Crisp. Confident. Probably worth something.", "✒️"),
    Material("compliance_artifact", "Compliance Artifact", "LEGENDARY",
             "Audit-grade evidence. Handle with extreme care.", "🛡️"),
]}


# Drop table — gates per stage tier. Each stage has a chance to drop one of
# these materials on win. Higher-tier mats cap at lower stages so progression
# is meaningful.
def _drops_for_stage_order(order: int) -> list[MaterialDrop]:
    """Material drop chances per stage order. Combat router rolls these
    after a successful battle in addition to normal gear drops.
    """
    if order <= 0:    # tutorial — no drops
        return []
    if order <= 3:    # early game
        return [
            MaterialDrop("rusted_keyboard_key", chance=0.40, qty_min=1, qty_max=2),
            MaterialDrop("expired_certificate", chance=0.20),
        ]
    if order <= 7:    # mid game
        return [
            MaterialDrop("rusted_keyboard_key", chance=0.35, qty_min=1, qty_max=3),
            MaterialDrop("expired_certificate", chance=0.30, qty_min=1, qty_max=2),
            MaterialDrop("legacy_punch_card", chance=0.18),
        ]
    if order <= 12:   # late game
        return [
            MaterialDrop("expired_certificate", chance=0.30, qty_min=1, qty_max=3),
            MaterialDrop("legacy_punch_card", chance=0.25, qty_min=1, qty_max=2),
            MaterialDrop("on_call_token", chance=0.18),
            MaterialDrop("ceo_signature", chance=0.05),
        ]
    # endgame
    return [
        MaterialDrop("legacy_punch_card", chance=0.30, qty_min=1, qty_max=3),
        MaterialDrop("on_call_token", chance=0.25, qty_min=1, qty_max=2),
        MaterialDrop("ceo_signature", chance=0.10),
        MaterialDrop("compliance_artifact", chance=0.04),
    ]


# Raid attacks drop a richer pool — guild content earns better mats.
RAID_MATERIAL_DROPS: list[MaterialDrop] = [
    MaterialDrop("on_call_token", chance=0.45, qty_min=1, qty_max=3),
    MaterialDrop("ceo_signature", chance=0.18, qty_min=1, qty_max=2),
    MaterialDrop("compliance_artifact", chance=0.06),
]


# Recipes — keep them small at first; expand once players are trying them out.
RECIPES: dict[str, Recipe] = {r.code: r for r in [
    Recipe(
        code="convert_keys_to_shards",
        name="Pawn Old Keyboards",
        description="The IT supply closet pays scrap for these.",
        materials={"rusted_keyboard_key": 5},
        coin_cost=200,
        output={"shards": 10},
        icon="🔧",
    ),
    Recipe(
        code="renew_certificates",
        name="Renew Old Certificates",
        description="Bundle three expired certs and quietly re-sign them.",
        materials={"expired_certificate": 3},
        output={"gems": 30},
        icon="📜",
    ),
    Recipe(
        code="forge_punch_card_pack",
        name="Mainframe Reactivation",
        description="Punch the right cards in the right order — the system honors it.",
        materials={"legacy_punch_card": 4, "rusted_keyboard_key": 2},
        coin_cost=500,
        output={"shards": 30, "access_cards": 1},
        icon="🃏",
    ),
    Recipe(
        code="pager_summon_token",
        name="Forge a Free Summon",
        description="Three on-call tokens, two CEO signatures, and the Universe owes you one.",
        materials={"on_call_token": 3, "ceo_signature": 2},
        coin_cost=1000,
        gem_cost=50,
        output={"free_summon_credits": 1},
        icon="🎫",
    ),
    Recipe(
        code="audit_jackpot",
        name="Audit Jackpot",
        description="Hand the compliance artifact to the right department. Get paid.",
        materials={"compliance_artifact": 1, "ceo_signature": 3},
        coin_cost=2000,
        output={"gems": 500, "shards": 100, "access_cards": 5},
        icon="🛡️",
    ),
]}


# --- Per-account inventory helpers ------------------------------------------


def grant_material(db: Session, account: Account, code: str, qty: int) -> int:
    """Add `qty` of a material to the account's inventory. Returns new total."""
    if qty <= 0 or code not in MATERIALS:
        return current_qty(db, account, code)
    row = db.scalar(
        select(CraftMaterial).where(
            CraftMaterial.account_id == account.id,
            CraftMaterial.code == code,
        )
    )
    if row is None:
        row = CraftMaterial(account_id=account.id, code=code, quantity=int(qty))
        db.add(row)
    else:
        row.quantity = int(row.quantity) + int(qty)
    db.flush()
    return int(row.quantity)


def current_qty(db: Session, account: Account, code: str) -> int:
    row = db.scalar(
        select(CraftMaterial).where(
            CraftMaterial.account_id == account.id,
            CraftMaterial.code == code,
        )
    )
    return int(row.quantity) if row else 0


def all_materials(db: Session, account: Account) -> dict[str, int]:
    """Return {code: qty} for everything the account holds, including zero
    rows (so the UI can show a complete grid)."""
    rows = db.scalars(
        select(CraftMaterial).where(CraftMaterial.account_id == account.id)
    )
    inv = {r.code: int(r.quantity) for r in rows}
    # Always seed every catalog code so the UI doesn't have to special-case.
    return {code: inv.get(code, 0) for code in MATERIALS}


# --- Drop hooks (called from battles + raids) -------------------------------


def roll_battle_drops(rng: random.Random, stage_order: int) -> list[tuple[str, int]]:
    """Return [(material_code, qty)] dropped from a single battle win."""
    out: list[tuple[str, int]] = []
    for drop in _drops_for_stage_order(stage_order):
        if rng.random() < drop.chance:
            qty = rng.randint(drop.qty_min, drop.qty_max)
            out.append((drop.material_code, qty))
    return out


def roll_raid_drops(rng: random.Random) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for drop in RAID_MATERIAL_DROPS:
        if rng.random() < drop.chance:
            qty = rng.randint(drop.qty_min, drop.qty_max)
            out.append((drop.material_code, qty))
    return out


# --- Crafting (the actual exchange) -----------------------------------------


def _grant_recipe_output(db: Session, account: Account, output: dict) -> dict:
    """Apply a recipe's output dict. Mirrors store.apply_grant but doesn't
    touch the PurchaseLedger (crafting is off-ledger; not a real purchase).
    """
    granted: dict = {}
    for kind in ("gems", "shards", "coins", "access_cards"):
        amount = int(output.get(kind, 0) or 0)
        if amount > 0:
            setattr(account, kind, getattr(account, kind) + amount)
            granted[kind] = amount

    free = int(output.get("free_summon_credits", 0) or 0)
    if free > 0:
        account.free_summon_credits = (account.free_summon_credits or 0) + free
        granted["free_summon_credits"] = free

    code = output.get("hero_template_code")
    if code:
        tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
        if tmpl is None:
            raise ValueError(f"recipe references missing hero template {code!r}")
        hero = HeroInstance(account_id=account.id, template_id=tmpl.id)
        db.add(hero)
        db.flush()
        granted["hero_instance_id"] = hero.id
        granted["hero_name"] = tmpl.name
    return granted


def craft(db: Session, account: Account, recipe_code: str, *, multiplier: int = 1) -> dict:
    """Atomic: validate inputs, deduct everything, grant output. Caller commits.

    Raises ValueError on any input/balance failure. Returns the granted dict.
    `multiplier` lets one call craft N copies of a recipe in one transaction.
    """
    if multiplier < 1:
        raise ValueError("multiplier must be >= 1")
    recipe = RECIPES.get(recipe_code)
    if recipe is None:
        raise ValueError(f"unknown recipe {recipe_code!r}")

    # Validate every cost first so we don't half-apply on failure.
    for code, qty in recipe.materials.items():
        need = qty * multiplier
        if current_qty(db, account, code) < need:
            raise ValueError(f"need {need}× {code} (have {current_qty(db, account, code)})")
    if account.coins < recipe.coin_cost * multiplier:
        raise ValueError(f"need {recipe.coin_cost * multiplier} coins")
    if account.gems < recipe.gem_cost * multiplier:
        raise ValueError(f"need {recipe.gem_cost * multiplier} gems")

    # Deduct.
    spent_inputs: dict[str, int] = {}
    for code, qty in recipe.materials.items():
        amount = qty * multiplier
        row = db.scalar(
            select(CraftMaterial).where(
                CraftMaterial.account_id == account.id,
                CraftMaterial.code == code,
            )
        )
        row.quantity = int(row.quantity) - amount
        spent_inputs[code] = amount
    if recipe.coin_cost:
        account.coins -= recipe.coin_cost * multiplier
        spent_inputs["coins"] = recipe.coin_cost * multiplier
    if recipe.gem_cost:
        account.gems -= recipe.gem_cost * multiplier
        spent_inputs["gems"] = recipe.gem_cost * multiplier

    # Grant output (×multiplier).
    full_granted: dict = {}
    for _ in range(multiplier):
        granted = _grant_recipe_output(db, account, recipe.output)
        for k, v in granted.items():
            if isinstance(v, int):
                full_granted[k] = full_granted.get(k, 0) + v
            else:
                full_granted.setdefault(k, []).append(v) if k.endswith("_ids") else full_granted.update({k: v})

    # Audit log row.
    summary_bits = [f"+{v} {k}" for k, v in full_granted.items() if isinstance(v, int)]
    db.add(CraftLog(
        account_id=account.id,
        recipe_code=recipe.code,
        inputs_json=json.dumps(spent_inputs),
        output_summary=", ".join(summary_bits)[:256],
    ))
    db.flush()
    return full_granted


def list_recipe_dicts() -> list[dict]:
    """Catalog as a list of plain dicts for the API/UI. Read-only — recipes
    are content-as-code so we don't mutate this in place."""
    out = []
    for r in RECIPES.values():
        out.append({
            "code": r.code,
            "name": r.name,
            "description": r.description,
            "materials": dict(r.materials),
            "coin_cost": r.coin_cost,
            "gem_cost": r.gem_cost,
            "output": dict(r.output),
            "icon": r.icon,
        })
    return out
