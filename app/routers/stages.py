import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.drop_meter import DROP_METER_CAP
from app.economy import load_cleared
from app.models import Account, Stage, StageDifficulty, STAGE_TIER_DISPLAY
from app.schemas import StageOut
from app.tiers import tier_power_floor

router = APIRouter(prefix="/stages", tags=["stages"])


def _load_drop_meter_dict(account: Account) -> dict:
    try:
        return json.loads(account.stage_drop_pity_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _stage_out(s: Stage, cleared: set[str], drop_meter_dict: dict) -> StageOut:
    try:
        waves = json.loads(s.waves_json or "[]")
    except json.JSONDecodeError:
        waves = []
    try:
        tier_enum = s.difficulty_tier if isinstance(s.difficulty_tier, StageDifficulty) else StageDifficulty(s.difficulty_tier)
        display = STAGE_TIER_DISPLAY.get(tier_enum, str(s.difficulty_tier))
    except ValueError:
        display = str(s.difficulty_tier)
    unlocked = (not s.requires_code) or (s.requires_code in cleared)
    is_cleared = s.code in cleared
    floor = tier_power_floor(s.difficulty_tier)
    tier_str = tier_enum.value if isinstance(tier_enum, StageDifficulty) else str(s.difficulty_tier)
    meter_key = f"{s.code}:{tier_str}"
    meter = int(drop_meter_dict.get(meter_key, 0))
    return StageOut(
        id=s.id,
        code=s.code,
        name=s.name,
        order=s.order,
        energy_cost=s.energy_cost,
        recommended_power=s.recommended_power,
        waves=waves,
        coin_reward=s.coin_reward,
        first_clear_gems=s.first_clear_gems,
        first_clear_shards=s.first_clear_shards,
        difficulty_tier=str(s.difficulty_tier),
        requires_code=s.requires_code,
        display_name=display,
        unlocked=unlocked,
        cleared=is_cleared,
        power_floor=floor,
        drop_meter=meter,
        drop_meter_cap=DROP_METER_CAP,
    )


@router.get("", response_model=list[StageOut])
def list_stages(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StageOut]:
    cleared = load_cleared(account)
    meters = _load_drop_meter_dict(account)
    return [_stage_out(s, cleared, meters) for s in db.scalars(select(Stage).order_by(Stage.order))]


@router.get("/{stage_id}", response_model=StageOut)
def get_stage(
    stage_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> StageOut:
    s = db.get(Stage, stage_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")
    cleared = load_cleared(account)
    meters = _load_drop_meter_dict(account)
    return _stage_out(s, cleared, meters)
