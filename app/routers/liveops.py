from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.liveops import liveops_summary

router = APIRouter(prefix="/liveops", tags=["liveops"])


@router.get("/active", response_model=list[dict])
def active(db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    return liveops_summary(db)
