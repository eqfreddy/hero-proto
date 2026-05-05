"""Notification stream — list, unread count, mark read, clear all."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, desc, func, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.models import Account, DeviceToken, Notification, utcnow

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


# ---------------------------------------------------------------------------
# Device-token management (Capacitor push notifications)
# ---------------------------------------------------------------------------

_VALID_PLATFORMS = {"fcm", "apns"}


class DeviceTokenIn(BaseModel):
    token: str
    platform: str  # 'fcm' | 'apns'


@router.post("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def register_device_token(
    body: DeviceTokenIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Register or refresh a push-notification device token.

    Call on app foreground after Capacitor's PushNotifications.register()
    resolves. Upserts by token so duplicate calls are safe.
    """
    platform = body.platform.lower()
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"platform must be one of {sorted(_VALID_PLATFORMS)}")

    token = body.token.strip()[:512]
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "token must not be empty")

    existing = db.scalar(select(DeviceToken).where(DeviceToken.token == token))
    if existing:
        existing.account_id = account.id
        existing.last_seen_at = utcnow()
    else:
        db.add(DeviceToken(account_id=account.id, token=token, platform=platform))
    db.commit()
    return None


@router.delete("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device_token(
    body: DeviceTokenIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Deregister a device token on logout or app uninstall notification."""
    db.execute(
        sa_delete(DeviceToken).where(
            DeviceToken.token == body.token,
            DeviceToken.account_id == account.id,
        )
    )
    db.commit()
    return None
