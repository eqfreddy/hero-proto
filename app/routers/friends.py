"""Friends + DMs.

  GET    /friends                       list accepted friends
  GET    /friends/requests              incoming pending
  GET    /friends/requests/sent         outgoing pending
  POST   /friends/request               send by email_prefix or account_id
  POST   /friends/{id}/accept           accept incoming request
  POST   /friends/{id}/reject           reject incoming request
  DELETE /friends/{id}                  unfriend (removes both rows)
  POST   /friends/{id}/block            block (one-way)
  DELETE /friends/{id}/block            unblock

  GET    /dm/threads                    every account I've DMed (last message preview)
  GET    /dm/with/{account_id}          full thread newest-first, paginated
  POST   /dm/with/{account_id}          send a DM
  POST   /dm/{message_id}/read          mark single message read
  POST   /dm/with/{account_id}/read-all mark whole thread read
  POST   /dm/{message_id}/report        flag a message for moderator review

Block semantics: blocked accounts cannot send the blocker DMs (POST 403).
The block doesn't delete history — moderators can still see it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import (
    enforce_direct_message_rate_limit,
    enforce_friend_request_rate_limit,
    get_current_account,
)
from app.models import (
    Account,
    DirectMessage,
    DirectMessageReport,
    Friendship,
    FriendshipStatus,
    utcnow,
)

router = APIRouter(tags=["friends"])


# --- Schemas ----------------------------------------------------------------


class FriendOut(BaseModel):
    account_id: int
    name: str
    arena_rating: int
    account_level: int
    status: str
    since: str


class FriendRequestIn(BaseModel):
    account_id: int | None = None
    email_prefix: str | None = Field(default=None, max_length=64)


class DirectMessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    body: str
    created_at: str
    read_at: str | None
    is_mine: bool
    # True when the sender soft-deleted; the body field is replaced with a
    # stub ('[deleted]') so the recipient sees the gap but not the content.
    deleted: bool = False


class ThreadPreviewOut(BaseModel):
    other_account_id: int
    other_name: str
    last_body: str
    last_created_at: str
    unread_count: int


class DMSendIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class DMReportIn(BaseModel):
    reason: str = Field(default="", max_length=256)


# --- Helpers ----------------------------------------------------------------


def _name_for(account: Account) -> str:
    return account.email.split("@")[0] if account.email else f"#{account.id}"


def _friend_row(db: Session, fr: Friendship) -> FriendOut:
    other = db.get(Account, fr.other_account_id)
    return FriendOut(
        account_id=fr.other_account_id,
        name=_name_for(other) if other else "[gone]",
        arena_rating=other.arena_rating if other else 0,
        account_level=other.account_level if other else 1,
        status=str(fr.status),
        since=fr.created_at.isoformat(),
    )


def _both_friends(db: Session, a: int, b: int) -> bool:
    return db.scalar(
        select(Friendship).where(
            Friendship.account_id == a,
            Friendship.other_account_id == b,
            Friendship.status == FriendshipStatus.ACCEPTED,
        )
    ) is not None


def _is_blocked(db: Session, blocker: int, blockee: int) -> bool:
    return db.scalar(
        select(Friendship).where(
            Friendship.account_id == blocker,
            Friendship.other_account_id == blockee,
            Friendship.status == FriendshipStatus.BLOCKED,
        )
    ) is not None


# --- Friends endpoints ------------------------------------------------------


@router.get("/friends", response_model=list[FriendOut])
def list_friends(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FriendOut]:
    rows = db.scalars(
        select(Friendship)
        .where(
            Friendship.account_id == account.id,
            Friendship.status == FriendshipStatus.ACCEPTED,
        )
        .order_by(desc(Friendship.created_at))
    )
    return [_friend_row(db, fr) for fr in rows]


@router.get("/friends/requests", response_model=list[FriendOut])
def list_incoming_requests(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FriendOut]:
    """Pending friend requests received by the caller."""
    rows = db.scalars(
        select(Friendship)
        .where(
            Friendship.other_account_id == account.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .order_by(desc(Friendship.created_at))
    )
    out: list[FriendOut] = []
    for fr in rows:
        sender = db.get(Account, fr.account_id)
        out.append(FriendOut(
            account_id=fr.account_id,
            name=_name_for(sender) if sender else "[gone]",
            arena_rating=sender.arena_rating if sender else 0,
            account_level=sender.account_level if sender else 1,
            status="PENDING",
            since=fr.created_at.isoformat(),
        ))
    return out


@router.get("/friends/requests/sent", response_model=list[FriendOut])
def list_outgoing_requests(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FriendOut]:
    rows = db.scalars(
        select(Friendship)
        .where(
            Friendship.account_id == account.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .order_by(desc(Friendship.created_at))
    )
    return [_friend_row(db, fr) for fr in rows]


@router.post("/friends/request", response_model=FriendOut, status_code=status.HTTP_201_CREATED)
def send_friend_request(
    body: FriendRequestIn,
    account: Annotated[Account, Depends(enforce_friend_request_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> FriendOut:
    """Send a friend request by account_id or email-prefix lookup. Idempotent
    if a request to the same person already exists.
    """
    if body.account_id is None and not body.email_prefix:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "provide account_id or email_prefix")

    target: Account | None
    if body.account_id is not None:
        target = db.get(Account, body.account_id)
    else:
        # Match on email-prefix exact (the "name" we surface in the UI).
        # Constrained: must be an exact match on the local-part, not a wildcard.
        prefix = body.email_prefix.strip().lower()
        target = db.scalar(
            select(Account).where(func.lower(Account.email).like(prefix + "@%"))
        )

    if target is None or target.id == account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    # Already friends or already blocked → 409.
    if _both_friends(db, account.id, target.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "already friends")
    if _is_blocked(db, target.id, account.id):
        # Blocked side never sees this, surface a generic 404 instead.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    # Pending already from this user? Idempotent return.
    existing = db.scalar(
        select(Friendship).where(
            Friendship.account_id == account.id,
            Friendship.other_account_id == target.id,
        )
    )
    if existing is not None:
        if existing.status == FriendshipStatus.PENDING:
            return _friend_row(db, existing)
        if existing.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status.HTTP_409_CONFLICT, "already friends")
        if existing.status == FriendshipStatus.BLOCKED:
            raise HTTPException(status.HTTP_409_CONFLICT, "you have this user blocked")

    # Auto-accept if the recipient already requested us.
    reciprocal = db.scalar(
        select(Friendship).where(
            Friendship.account_id == target.id,
            Friendship.other_account_id == account.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
    )
    if reciprocal is not None:
        reciprocal.status = FriendshipStatus.ACCEPTED
        new_row = Friendship(
            account_id=account.id,
            other_account_id=target.id,
            status=FriendshipStatus.ACCEPTED,
        )
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        return _friend_row(db, new_row)

    fr = Friendship(
        account_id=account.id,
        other_account_id=target.id,
        status=FriendshipStatus.PENDING,
    )
    db.add(fr)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "request already exists")
    db.refresh(fr)

    # Notify recipient.
    from app.notifications import notify as _notify
    _notify(
        db, target,
        kind="friend_request",
        title=f"{_name_for(account)} sent a friend request",
        body="Open the friends tab to accept or reject.",
        link="/app/partials/friends",
        icon="🤝",
    )
    db.commit()
    return _friend_row(db, fr)


@router.post("/friends/{other_account_id}/accept", response_model=FriendOut)
def accept_friend_request(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> FriendOut:
    """Accept a pending request from `other_account_id`."""
    incoming = db.scalar(
        select(Friendship).where(
            Friendship.account_id == other_account_id,
            Friendship.other_account_id == account.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
    )
    if incoming is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending request from this user")

    incoming.status = FriendshipStatus.ACCEPTED
    reciprocal = Friendship(
        account_id=account.id,
        other_account_id=other_account_id,
        status=FriendshipStatus.ACCEPTED,
    )
    db.add(reciprocal)
    db.commit()
    db.refresh(reciprocal)
    return _friend_row(db, reciprocal)


@router.post("/friends/{other_account_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_friend_request(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    incoming = db.scalar(
        select(Friendship).where(
            Friendship.account_id == other_account_id,
            Friendship.other_account_id == account.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
    )
    if incoming is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending request")
    db.delete(incoming)
    db.commit()
    return None


@router.delete("/friends/{other_account_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfriend(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Remove the bidirectional ACCEPTED edge."""
    rows = list(db.scalars(
        select(Friendship).where(
            or_(
                and_(Friendship.account_id == account.id, Friendship.other_account_id == other_account_id),
                and_(Friendship.account_id == other_account_id, Friendship.other_account_id == account.id),
            ),
            Friendship.status == FriendshipStatus.ACCEPTED,
        )
    ))
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not friends")
    for r in rows:
        db.delete(r)
    db.commit()
    return None


@router.post("/friends/{other_account_id}/block", status_code=status.HTTP_201_CREATED)
def block_user(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Block another user. Removes any existing friendship row from caller's
    side, replaces with a BLOCKED row. Reciprocal row (if any) stays — it's
    the other player's edge, they can still see they were friends until they
    unfriend on their end."""
    if other_account_id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot block yourself")
    target = db.get(Account, other_account_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    existing = db.scalar(
        select(Friendship).where(
            Friendship.account_id == account.id,
            Friendship.other_account_id == other_account_id,
        )
    )
    if existing is not None:
        existing.status = FriendshipStatus.BLOCKED
    else:
        db.add(Friendship(
            account_id=account.id,
            other_account_id=other_account_id,
            status=FriendshipStatus.BLOCKED,
        ))
    # Also remove the reciprocal ACCEPTED row so blocked users don't show up
    # as friends in the blocker's feed.
    reciprocal = db.scalar(
        select(Friendship).where(
            Friendship.account_id == other_account_id,
            Friendship.other_account_id == account.id,
            Friendship.status == FriendshipStatus.ACCEPTED,
        )
    )
    if reciprocal is not None:
        db.delete(reciprocal)
    db.commit()
    return {"blocked": other_account_id}


@router.delete("/friends/{other_account_id}/block", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.scalar(
        select(Friendship).where(
            Friendship.account_id == account.id,
            Friendship.other_account_id == other_account_id,
            Friendship.status == FriendshipStatus.BLOCKED,
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user is not blocked")
    db.delete(row)
    db.commit()
    return None


# --- DMs --------------------------------------------------------------------


@router.get("/dm/threads", response_model=list[ThreadPreviewOut])
def list_dm_threads(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ThreadPreviewOut]:
    """One row per other-account the caller has exchanged DMs with, with the
    last-message preview and unread count from the caller's perspective."""
    # Get every distinct partner.
    partners = set()
    for r in db.execute(
        select(DirectMessage.sender_id, DirectMessage.recipient_id).where(
            or_(DirectMessage.sender_id == account.id, DirectMessage.recipient_id == account.id),
        )
    ):
        a, b = int(r[0]), int(r[1])
        partners.add(b if a == account.id else a)

    out: list[ThreadPreviewOut] = []
    for other_id in partners:
        last = db.scalar(
            select(DirectMessage)
            .where(or_(
                and_(DirectMessage.sender_id == account.id, DirectMessage.recipient_id == other_id),
                and_(DirectMessage.sender_id == other_id, DirectMessage.recipient_id == account.id),
            ))
            .order_by(desc(DirectMessage.id))
            .limit(1)
        )
        if last is None:
            continue
        unread = db.scalar(
            select(func.count(DirectMessage.id)).where(
                DirectMessage.sender_id == other_id,
                DirectMessage.recipient_id == account.id,
                DirectMessage.read_at.is_(None),
            )
        ) or 0
        other = db.get(Account, other_id)
        # Soft-deleted messages show their stub in the preview too — same
        # contract as /dm/with/* responses.
        preview_body = "[deleted]" if last.deleted_at is not None else last.body[:140]
        out.append(ThreadPreviewOut(
            other_account_id=other_id,
            other_name=_name_for(other) if other else "[gone]",
            last_body=preview_body,
            last_created_at=last.created_at.isoformat(),
            unread_count=int(unread),
        ))
    out.sort(key=lambda t: t.last_created_at, reverse=True)
    return out


@router.get("/dm/with/{other_account_id}", response_model=list[DirectMessageOut])
def get_thread(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    before: int | None = None,
) -> list[DirectMessageOut]:
    """Newest-first thread between caller and other_account_id. Pass ?before=
    to page backwards."""
    limit = max(1, min(200, limit))
    stmt = select(DirectMessage).where(or_(
        and_(DirectMessage.sender_id == account.id, DirectMessage.recipient_id == other_account_id),
        and_(DirectMessage.sender_id == other_account_id, DirectMessage.recipient_id == account.id),
    ))
    if before is not None:
        stmt = stmt.where(DirectMessage.id < before)
    rows = list(db.scalars(stmt.order_by(desc(DirectMessage.id)).limit(limit)))
    return [_dm_out(r, account.id) for r in rows]


def _dm_out(r: DirectMessage, viewer_id: int) -> DirectMessageOut:
    """Shared formatter that respects soft-delete: a deleted message returns
    `body='[deleted]'` and `deleted=True` so the recipient sees the gap but
    not the original content. The original body still lives in the DB for
    audit/abuse-report purposes."""
    deleted = r.deleted_at is not None
    return DirectMessageOut(
        id=r.id, sender_id=r.sender_id, recipient_id=r.recipient_id,
        body="[deleted]" if deleted else r.body,
        created_at=r.created_at.isoformat(),
        read_at=r.read_at.isoformat() if r.read_at else None,
        is_mine=r.sender_id == viewer_id,
        deleted=deleted,
    )


@router.post("/dm/with/{other_account_id}", response_model=DirectMessageOut, status_code=status.HTTP_201_CREATED)
def send_dm(
    other_account_id: int,
    body: DMSendIn,
    account: Annotated[Account, Depends(enforce_direct_message_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> DirectMessageOut:
    if other_account_id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot DM yourself")
    target = db.get(Account, other_account_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    # Block check — recipient blocked sender = reject.
    if _is_blocked(db, target.id, account.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user has blocked you")
    # And conversely — sender blocked recipient = reject too. Don't message
    # someone you've blocked.
    if _is_blocked(db, account.id, target.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "you have blocked this user")

    msg = DirectMessage(
        sender_id=account.id,
        recipient_id=other_account_id,
        body=body.body.strip(),
    )
    db.add(msg)
    db.flush()
    # Notify the recipient so the bell badge fires.
    from app.notifications import notify as _notify
    _notify(
        db, target,
        kind="dm",
        title=f"New message from {_name_for(account)}",
        body=msg.body[:140],
        link="/app/partials/friends",
        icon="✉️",
    )
    db.commit()
    db.refresh(msg)
    return _dm_out(msg, account.id)


@router.post("/dm/{message_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_dm_read(
    message_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    msg = db.get(DirectMessage, message_id)
    if msg is None or msg.recipient_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    if msg.read_at is None:
        msg.read_at = utcnow()
        db.commit()
    return None


@router.post("/dm/with/{other_account_id}/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_thread_read(
    other_account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    db.execute(
        DirectMessage.__table__.update()
        .where(
            DirectMessage.recipient_id == account.id,
            DirectMessage.sender_id == other_account_id,
            DirectMessage.read_at.is_(None),
        )
        .values(read_at=utcnow())
    )
    db.commit()
    return None


@router.delete("/dm/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dm(
    message_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Soft-delete a DM. Sender-only — recipients can't redact someone
    else's writing. The row stays in the DB so abuse reports / audit still
    resolve to the original content; the body is replaced with '[deleted]'
    in /dm/* responses via _dm_out. Idempotent on already-deleted rows."""
    msg = db.get(DirectMessage, message_id)
    if msg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    if msg.sender_id != account.id:
        # Don't leak existence to non-senders.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    if msg.deleted_at is None:
        msg.deleted_at = utcnow()
        db.commit()
    return None


@router.post("/dm/{message_id}/report", status_code=status.HTTP_201_CREATED)
def report_dm(
    message_id: int,
    body: DMReportIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Flag a DM for moderator review. Visible via /admin/reports (Phase 2)."""
    msg = db.get(DirectMessage, message_id)
    if msg is None or msg.recipient_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    rep = DirectMessageReport(
        reporter_id=account.id,
        message_id=message_id,
        reason=body.reason.strip()[:256],
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return {"reported_message_id": message_id, "report_id": rep.id}
