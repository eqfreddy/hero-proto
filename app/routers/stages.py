import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Stage
from app.schemas import StageOut

router = APIRouter(prefix="/stages", tags=["stages"])


def stage_out(s: Stage) -> StageOut:
    try:
        waves = json.loads(s.waves_json or "[]")
    except json.JSONDecodeError:
        waves = []
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
    )


@router.get("", response_model=list[StageOut])
def list_stages(db: Annotated[Session, Depends(get_db)]) -> list[StageOut]:
    return [stage_out(s) for s in db.scalars(select(Stage).order_by(Stage.order))]


@router.get("/{stage_id}", response_model=StageOut)
def get_stage(stage_id: int, db: Annotated[Session, Depends(get_db)]) -> StageOut:
    s = db.get(Stage, stage_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")
    return stage_out(s)
