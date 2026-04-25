"""Notification stream — list, unread count, mark read, clear all."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.models import Account, Notification, utcnow

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    link: str
    icon: str
    created_at: str
    read_at: str | None


class NotificationsListOut(BaseModel):
    unread_count: int
    items: list[NotificationOut]


@router.get("", response_model=NotificationsListOut)
def list_notifications(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    only_unread: bool = False,
) -> NotificationsListOut:
    limit = max(1, min(200, limit))
    stmt = select(Notification).where(Notification.account_id == account.id)
    if only_unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = list(db.scalars(stmt.order_by(desc(Notification.id)).limit(limit)))
    unread = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.account_id == account.id,
            Notification.read_at.is_(None),
        )
    ) or 0
    return NotificationsListOut(
        unread_count=int(unread),
        items=[
            NotificationOut(
                id=n.id, kind=n.kind, title=n.title, body=n.body,
                link=n.link, icon=n.icon,
                created_at=n.created_at.isoformat(),
                read_at=n.read_at.isoformat() if n.read_at else None,
            )
            for n in rows
        ],
    )


@router.get("/unread-count")
def unread_count(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Cheap polling endpoint — bell badge calls this every N seconds."""
    n = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.account_id == account.id,
            Notification.read_at.is_(None),
        )
    ) or 0
    return {"unread": int(n)}


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    notification_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    n = db.get(Notification, notification_id)
    if n is None or n.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return None


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    db.execute(
        update(Notification)
        .where(Notification.account_id == account.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_all(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Wipe every notification for the caller. Read or unread."""
    db.query(Notification).filter(Notification.account_id == account.id).delete()
    db.commit()
    return None
