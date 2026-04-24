from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.liveops import liveops_summary, scheduled_summary

router = APIRouter(prefix="/liveops", tags=["liveops"])


@router.get("/active", response_model=list[dict])
def active(db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    return liveops_summary(db)


@router.get("/scheduled", response_model=list[dict])
def scheduled(
    db: Annotated[Session, Depends(get_db)],
    horizon_days: int = 7,
) -> list[dict]:
    """Events that haven't started yet but begin within `horizon_days`."""
    horizon_days = max(1, min(90, horizon_days))
    return scheduled_summary(db, horizon_days=horizon_days)
