"""Server-wide MOTD / broadcast announcements.

Admin creates / deletes via /admin/announcements/*. Public reads /announcements/active.
Active = is_active AND starts_at <= now < (ends_at or +infinity).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import Account, AdminAnnouncement, utcnow

public = APIRouter(prefix="/announcements", tags=["announcements"])
admin = APIRouter(prefix="/admin/announcements", tags=["admin-announcements"])


class AnnouncementOut(BaseModel):
    id: int
    title: str
    body: str
    priority: int
    starts_at: datetime
    ends_at: datetime | None
    is_active: bool
    created_by: int | None
    created_at: datetime


class AnnouncementCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1, max_length=2048)
    priority: int = Field(default=0, ge=0, le=100)
    duration_hours: float | None = Field(default=None, gt=0, le=24 * 365)
    starts_at: datetime | None = None


class AnnouncementUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    body: str | None = Field(default=None, min_length=1, max_length=2048)
    priority: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    ends_at: datetime | None = None


def _out(a: AdminAnnouncement) -> AnnouncementOut:
    return AnnouncementOut(
        id=a.id, title=a.title, body=a.body, priority=a.priority,
        starts_at=a.starts_at, ends_at=a.ends_at, is_active=a.is_active,
        created_by=a.created_by, created_at=a.created_at,
    )


@public.get("/active", response_model=list[AnnouncementOut])
def active_announcements(db: Annotated[Session, Depends(get_db)]) -> list[AnnouncementOut]:
    """Currently visible announcements, highest-priority first."""
    now = utcnow()
    rows = db.scalars(
        select(AdminAnnouncement)
        .where(
            AdminAnnouncement.is_active.is_(True),
            AdminAnnouncement.starts_at <= now,
        )
        .order_by(desc(AdminAnnouncement.priority), desc(AdminAnnouncement.id))
    )
    return [_out(a) for a in rows if a.ends_at is None or a.ends_at > now]


@admin.post("", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
def create_announcement(
    body: AnnouncementCreateIn,
    admin_acct: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AnnouncementOut:
    now = utcnow()
    starts_at = body.starts_at or now
    ends_at = None
    if body.duration_hours is not None:
        from datetime import timedelta
        ends_at = starts_at + timedelta(hours=body.duration_hours)
    ann = AdminAnnouncement(
        title=body.title.strip(),
        body=body.body.strip(),
        priority=body.priority,
        starts_at=starts_at,
        ends_at=ends_at,
        is_active=True,
        created_by=admin_acct.id,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return _out(ann)


@admin.get("", response_model=list[AnnouncementOut])
def list_announcements(
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 100,
    include_inactive: bool = True,
) -> list[AnnouncementOut]:
    limit = max(1, min(500, limit))
    stmt = select(AdminAnnouncement).order_by(desc(AdminAnnouncement.id)).limit(limit)
    if not include_inactive:
        stmt = stmt.where(AdminAnnouncement.is_active.is_(True))
    return [_out(a) for a in db.scalars(stmt)]


@admin.patch("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    body: AnnouncementUpdateIn,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AnnouncementOut:
    a = db.get(AdminAnnouncement, announcement_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "announcement not found")
    if body.title is not None: a.title = body.title.strip()
    if body.body is not None: a.body = body.body.strip()
    if body.priority is not None: a.priority = body.priority
    if body.is_active is not None: a.is_active = body.is_active
    if body.ends_at is not None: a.ends_at = body.ends_at
    db.commit()
    db.refresh(a)
    return _out(a)


@admin.delete("/{announcement_id}", response_model=dict)
def delete_announcement(
    announcement_id: int,
    _admin: Annotated[Account, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    a = db.get(AdminAnnouncement, announcement_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "announcement not found")
    db.delete(a)
    db.commit()
    return {"deleted_id": announcement_id}
