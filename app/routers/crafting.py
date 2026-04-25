"""Crafting endpoints — materials inventory + recipe catalog + craft action.

  GET  /crafting/materials            caller's full material inventory
  GET  /crafting/recipes              recipe catalog (read-only, content-as-code)
  POST /crafting/{recipe_code}/craft  spend materials/currency, grant output

Catalog rules + drop tables live in app/crafting.py — admins do not edit
them via API. Want a new recipe? Edit the file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.crafting import (
    MATERIALS,
    RECIPES,
    all_materials,
    craft as craft_action,
    list_recipe_dicts,
)
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, CraftLog

router = APIRouter(prefix="/crafting", tags=["crafting"])


# --- schemas -----------------------------------------------------------------


class MaterialOut(BaseModel):
    code: str
    name: str
    rarity: str
    description: str
    icon: str
    quantity: int


class RecipeOut(BaseModel):
    code: str
    name: str
    description: str
    materials: dict[str, int]
    coin_cost: int
    gem_cost: int
    output: dict
    icon: str
    craftable: bool
    blocking_reason: str | None = None


class CraftIn(BaseModel):
    multiplier: int = Field(ge=1, le=10, default=1)


class CraftOut(BaseModel):
    recipe_code: str
    multiplier: int
    spent: dict       # snapshot of materials + currency consumed
    granted: dict     # output dict (from crafting._grant_recipe_output)
    materials_after: dict[str, int]


class CraftLogOut(BaseModel):
    id: int
    recipe_code: str
    inputs: dict
    output_summary: str
    created_at: str


# --- endpoints ---------------------------------------------------------------


@router.get("/materials", response_model=list[MaterialOut])
def list_my_materials(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MaterialOut]:
    """Always returns the full catalog so the UI can show zeros for materials
    the player hasn't pulled yet."""
    inv = all_materials(db, account)
    return [
        MaterialOut(
            code=m.code,
            name=m.name,
            rarity=m.rarity,
            description=m.description,
            icon=m.icon,
            quantity=inv.get(m.code, 0),
        )
        for m in MATERIALS.values()
    ]


@router.get("/recipes", response_model=list[RecipeOut])
def list_recipes(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RecipeOut]:
    """Catalog joined with affordability / craftability flags so the client
    doesn't have to re-derive them."""
    inv = all_materials(db, account)
    out: list[RecipeOut] = []
    for r_dict in list_recipe_dicts():
        # Compute craftability inline.
        reason = None
        for code, qty in r_dict["materials"].items():
            have = inv.get(code, 0)
            if have < qty:
                reason = f"need {qty - have} more {code}"
                break
        if reason is None and account.coins < r_dict["coin_cost"]:
            reason = f"need {r_dict['coin_cost'] - account.coins} coins"
        if reason is None and account.gems < r_dict["gem_cost"]:
            reason = f"need {r_dict['gem_cost'] - account.gems} gems"
        out.append(RecipeOut(
            **r_dict,
            craftable=reason is None,
            blocking_reason=reason,
        ))
    return out


@router.post("/{recipe_code}/craft", response_model=CraftOut, status_code=status.HTTP_201_CREATED)
def craft_recipe(
    recipe_code: str,
    body: CraftIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> CraftOut:
    if recipe_code not in RECIPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown recipe {recipe_code!r}")
    try:
        granted = craft_action(db, account, recipe_code, multiplier=body.multiplier)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e

    # Build a clean spent-snapshot from the recipe definition × multiplier.
    recipe = RECIPES[recipe_code]
    spent = {code: qty * body.multiplier for code, qty in recipe.materials.items()}
    if recipe.coin_cost:
        spent["coins"] = recipe.coin_cost * body.multiplier
    if recipe.gem_cost:
        spent["gems"] = recipe.gem_cost * body.multiplier

    db.commit()
    db.refresh(account)
    return CraftOut(
        recipe_code=recipe_code,
        multiplier=body.multiplier,
        spent=spent,
        granted=granted,
        materials_after=all_materials(db, account),
    )


@router.get("/log", response_model=list[CraftLogOut])
def list_my_craft_log(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 25,
) -> list[CraftLogOut]:
    import json
    limit = max(1, min(100, limit))
    rows = list(db.scalars(
        select(CraftLog)
        .where(CraftLog.account_id == account.id)
        .order_by(desc(CraftLog.id))
        .limit(limit)
    ))
    return [
        CraftLogOut(
            id=r.id,
            recipe_code=r.recipe_code,
            inputs=json.loads(r.inputs_json or "{}") if r.inputs_json else {},
            output_summary=r.output_summary,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
