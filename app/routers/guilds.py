from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import (
    enforce_guild_message_ip_rate_limit,
    enforce_guild_message_rate_limit,
    get_current_account,
)
from app.guild_achievements import _update_guild_achievement
from app.models import (
    Account,
    Guild,
    GuildAchievement,
    GuildAchievementProgress,
    GuildApplication,
    GuildApplicationStatus,
    GuildInvite,
    GuildMember,
    GuildMessage,
    GuildRole,
    utcnow,
)
from app.schemas import (
    GuildAchievementOut,
    GuildAchievementsResponse,
    GuildApplicationIn,
    GuildApplicationOut,
    GuildCreateIn,
    GuildDetailOut,
    GuildInviteIn,
    GuildInviteOut,
    GuildMemberOut,
    GuildMessageIn,
    GuildMessageOut,
    GuildOut,
    GuildUpdateIn,
)

router = APIRouter(prefix="/guilds", tags=["guilds"])

MAX_GUILD_SIZE = 30


def _member_count(db: Session, guild_id: int) -> int:
    return db.scalar(select(func.count(GuildMember.account_id)).where(GuildMember.guild_id == guild_id)) or 0


def _guild_out(db: Session, g: Guild) -> GuildOut:
    return GuildOut(
        id=g.id,
        name=g.name,
        tag=g.tag,
        description=g.description,
        member_count=_member_count(db, g.id),
    )


def _require_membership(db: Session, account: Account, guild_id: int) -> GuildMember:
    m = db.get(GuildMember, account.id)
    if m is None or m.guild_id != guild_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this guild")
    return m


@router.post("", response_model=GuildOut, status_code=status.HTTP_201_CREATED)
def create_guild(
    body: GuildCreateIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildOut:
    if db.get(GuildMember, account.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already in a guild — leave first")
    guild = Guild(
        name=body.name.strip(),
        tag=body.tag.upper().strip(),
        description=body.description.strip(),
        created_by=account.id,
    )
    db.add(guild)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "name or tag already taken") from exc
    db.add(GuildMember(account_id=account.id, guild_id=guild.id, role=GuildRole.LEADER))
    # Count the founder as the first member so FIRST_MEMBER (target=2) fires
    # when the next player joins, rather than never.
    _update_guild_achievement(db, guild.id, "members_joined", 1)
    db.commit()
    db.refresh(guild)
    return _guild_out(db, guild)


@router.get("", response_model=list[GuildOut])
def list_guilds(
    db: Annotated[Session, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[GuildOut]:
    """Paginated; server-enforced cap to prevent unbounded scans on a large server.
    Client can page through with offset; at high offsets this is slow but that's OK
    since it's the rare path (typical caller only looks at page 1)."""
    limit = max(1, min(500, limit))
    offset = max(0, offset)
    return [
        _guild_out(db, g)
        for g in db.scalars(select(Guild).order_by(Guild.id).offset(offset).limit(limit))
    ]


@router.get("/mine", response_model=GuildDetailOut | None)
def my_guild(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut | None:
    m = db.get(GuildMember, account.id)
    if m is None:
        return None
    return _detail(db, m.guild_id)


def _detail(db: Session, guild_id: int) -> GuildDetailOut | None:
    g = db.get(Guild, guild_id)
    if g is None:
        return None
    members_rows = db.execute(
        select(Account.id, Account.email, GuildMember.role, Account.arena_rating)
        .join(GuildMember, GuildMember.account_id == Account.id)
        .where(GuildMember.guild_id == guild_id)
        .order_by(Account.arena_rating.desc(), Account.id)
    )
    members = [
        GuildMemberOut(
            account_id=row[0],
            name=row[1].split("@")[0],
            role=GuildRole(row[2]) if not isinstance(row[2], GuildRole) else row[2],
            arena_rating=row[3],
        )
        for row in members_rows
    ]
    return GuildDetailOut(
        id=g.id,
        name=g.name,
        tag=g.tag,
        description=g.description,
        member_count=len(members),
        members=members,
    )


@router.get("/{guild_id}", response_model=GuildDetailOut)
def get_guild(guild_id: int, db: Annotated[Session, Depends(get_db)]) -> GuildDetailOut:
    d = _detail(db, guild_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guild not found")
    return d


@router.post("/{guild_id}/join", response_model=GuildDetailOut)
def join_guild(
    guild_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    g = db.get(Guild, guild_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guild not found")
    if db.get(GuildMember, account.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already in a guild — leave first")
    if _member_count(db, guild_id) >= MAX_GUILD_SIZE:
        raise HTTPException(status.HTTP_409_CONFLICT, "guild is full")
    db.add(GuildMember(account_id=account.id, guild_id=guild_id, role=GuildRole.MEMBER))
    _update_guild_achievement(db, guild_id, "members_joined", 1)
    db.commit()
    return _detail(db, guild_id)  # type: ignore[return-value]


@router.post("/leave", response_model=dict)
def leave_guild(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    m = db.get(GuildMember, account.id)
    if m is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not in a guild")
    guild_id = m.guild_id
    if m.role == GuildRole.LEADER:
        # If leader leaves, promote oldest remaining member — or disband if none.
        successor = db.scalar(
            select(GuildMember)
            .where(GuildMember.guild_id == guild_id, GuildMember.account_id != account.id)
            .order_by(GuildMember.joined_at)
        )
        if successor is not None:
            successor.role = GuildRole.LEADER
        else:
            # Disband: cascade-delete the guild.
            db.delete(db.get(Guild, guild_id))
    db.delete(m)
    db.commit()
    return {"left_guild_id": guild_id}


@router.put("/{guild_id}", response_model=GuildDetailOut)
def update_guild(
    guild_id: int,
    body: GuildUpdateIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    m = _require_membership(db, account, guild_id)
    if m.role not in (GuildRole.LEADER, GuildRole.OFFICER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leaders/officers only")
    g = db.get(Guild, guild_id)
    assert g is not None
    g.description = body.description.strip()
    db.commit()
    return _detail(db, guild_id)  # type: ignore[return-value]


@router.post("/{guild_id}/promote/{account_id}", response_model=GuildDetailOut)
def promote_member(
    guild_id: int,
    account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    """Leader promotes a MEMBER to OFFICER. Idempotent if target is already OFFICER."""
    m = _require_membership(db, account, guild_id)
    if m.role != GuildRole.LEADER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leader only")
    target = db.get(GuildMember, account_id)
    if target is None or target.guild_id != guild_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found in this guild")
    if target.role == GuildRole.LEADER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "target is already leader — use transfer")
    target.role = GuildRole.OFFICER
    db.commit()
    return _detail(db, guild_id)  # type: ignore[return-value]


@router.post("/{guild_id}/demote/{account_id}", response_model=GuildDetailOut)
def demote_member(
    guild_id: int,
    account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    """Leader demotes an OFFICER back to MEMBER."""
    m = _require_membership(db, account, guild_id)
    if m.role != GuildRole.LEADER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leader only")
    target = db.get(GuildMember, account_id)
    if target is None or target.guild_id != guild_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found in this guild")
    if target.role != GuildRole.OFFICER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "target is not an officer")
    target.role = GuildRole.MEMBER
    db.commit()
    return _detail(db, guild_id)  # type: ignore[return-value]


@router.post("/{guild_id}/transfer/{account_id}", response_model=GuildDetailOut)
def transfer_leadership(
    guild_id: int,
    account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    """Current leader hands off to another member; old leader becomes OFFICER."""
    m = _require_membership(db, account, guild_id)
    if m.role != GuildRole.LEADER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leader only")
    if account_id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot transfer to yourself")
    target = db.get(GuildMember, account_id)
    if target is None or target.guild_id != guild_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found in this guild")
    target.role = GuildRole.LEADER
    m.role = GuildRole.OFFICER
    db.commit()
    return _detail(db, guild_id)  # type: ignore[return-value]


@router.post("/{guild_id}/kick/{account_id}", response_model=GuildDetailOut)
def kick_member(
    guild_id: int,
    account_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    m = _require_membership(db, account, guild_id)
    if m.role != GuildRole.LEADER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leader only")
    if account_id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "use /guilds/leave to leave your own guild")
    victim = db.get(GuildMember, account_id)
    if victim is None or victim.guild_id != guild_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found in this guild")
    db.delete(victim)
    db.commit()
    return _detail(db, guild_id)  # type: ignore[return-value]


@router.get("/{guild_id}/messages", response_model=list[GuildMessageOut])
def list_messages(
    guild_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    before: int | None = None,
    limit: int = 50,
) -> list[GuildMessageOut]:
    """Newest-first. Pass ?before=<last_seen_id> to page backwards through history."""
    _require_membership(db, account, guild_id)
    limit = max(1, min(200, limit))
    stmt = (
        select(GuildMessage.id, GuildMessage.guild_id, GuildMessage.author_id, Account.email, GuildMessage.body, GuildMessage.created_at)
        .outerjoin(Account, Account.id == GuildMessage.author_id)
        .where(GuildMessage.guild_id == guild_id)
    )
    if before is not None:
        stmt = stmt.where(GuildMessage.id < before)
    rows = db.execute(stmt.order_by(GuildMessage.id.desc()).limit(limit))
    return [
        GuildMessageOut(
            id=row[0],
            guild_id=row[1],
            author_id=row[2],
            author_name=(row[3].split("@")[0] if row[3] else "[gone]"),
            body=row[4],
            created_at=row[5],
        )
        for row in rows
    ]


@router.post(
    "/{guild_id}/messages",
    response_model=GuildMessageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_guild_message_ip_rate_limit)],
)
def post_message(
    guild_id: int,
    body: GuildMessageIn,
    account: Annotated[Account, Depends(enforce_guild_message_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildMessageOut:
    _require_membership(db, account, guild_id)
    msg = GuildMessage(guild_id=guild_id, author_id=account.id, body=body.body.strip())
    db.add(msg)
    _update_guild_achievement(db, guild_id, "messages_sent", 1)
    db.commit()
    db.refresh(msg)
    return GuildMessageOut(
        id=msg.id,
        guild_id=msg.guild_id,
        author_id=msg.author_id,
        author_name=account.email.split("@")[0],
        body=msg.body,
        created_at=msg.created_at,
    )


# --- application / invite flow ------------------------------------------------


def _app_out(db: Session, a: GuildApplication) -> GuildApplicationOut:
    applicant = db.get(Account, a.account_id)
    name = applicant.email.split("@")[0] if applicant else "[gone]"
    return GuildApplicationOut(
        id=a.id,
        guild_id=a.guild_id,
        account_id=a.account_id,
        applicant_name=name,
        status=str(a.status),
        message=a.message,
        created_at=a.created_at,
        reviewed_at=a.reviewed_at,
        reviewed_by=a.reviewed_by,
    )


@router.post("/{guild_id}/apply", response_model=GuildApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_to_guild(
    guild_id: int,
    body: GuildApplicationIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildApplicationOut:
    """Submit an application. Caller must not already be in a guild."""
    g = db.get(Guild, guild_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guild not found")
    if db.get(GuildMember, account.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already in a guild — leave first")
    # Disallow a second PENDING to the same guild.
    existing = db.scalar(
        select(GuildApplication).where(
            GuildApplication.account_id == account.id,
            GuildApplication.guild_id == guild_id,
            GuildApplication.status == GuildApplicationStatus.PENDING,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "application already pending for this guild")
    app = GuildApplication(
        account_id=account.id,
        guild_id=guild_id,
        message=body.message.strip(),
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _app_out(db, app)


@router.get("/{guild_id}/applications", response_model=list[GuildApplicationOut])
def list_applications(
    guild_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    include_reviewed: bool = False,
) -> list[GuildApplicationOut]:
    """Officers and the leader see pending applications for their guild."""
    m = _require_membership(db, account, guild_id)
    if m.role not in (GuildRole.LEADER, GuildRole.OFFICER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leaders/officers only")
    stmt = select(GuildApplication).where(GuildApplication.guild_id == guild_id)
    if not include_reviewed:
        stmt = stmt.where(GuildApplication.status == GuildApplicationStatus.PENDING)
    stmt = stmt.order_by(GuildApplication.created_at.desc())
    return [_app_out(db, a) for a in db.scalars(stmt)]


@router.get("/applications/mine", response_model=list[GuildApplicationOut])
def list_my_applications(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[GuildApplicationOut]:
    """Caller's own applications (any status), newest first, capped per call."""
    limit = max(1, min(200, limit))
    rows = db.scalars(
        select(GuildApplication)
        .where(GuildApplication.account_id == account.id)
        .order_by(GuildApplication.created_at.desc())
        .limit(limit)
    )
    return [_app_out(db, a) for a in rows]


def _load_app_for_review(db: Session, account: Account, application_id: int) -> GuildApplication:
    a = db.get(GuildApplication, application_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "application not found")
    m = db.get(GuildMember, account.id)
    if m is None or m.guild_id != a.guild_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this guild")
    if m.role not in (GuildRole.LEADER, GuildRole.OFFICER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leaders/officers only")
    if a.status != GuildApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"application already {a.status}")
    return a


@router.post("/applications/{application_id}/accept", response_model=GuildDetailOut)
def accept_application(
    application_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    a = _load_app_for_review(db, account, application_id)
    # Applicant might have joined another guild in the meantime.
    if db.get(GuildMember, a.account_id) is not None:
        a.status = GuildApplicationStatus.REJECTED
        a.reviewed_at = utcnow()
        a.reviewed_by = account.id
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "applicant is now in another guild")
    if _member_count(db, a.guild_id) >= MAX_GUILD_SIZE:
        raise HTTPException(status.HTTP_409_CONFLICT, "guild is full")
    db.add(GuildMember(account_id=a.account_id, guild_id=a.guild_id, role=GuildRole.MEMBER))
    _update_guild_achievement(db, a.guild_id, "members_joined", 1)
    a.status = GuildApplicationStatus.ACCEPTED
    a.reviewed_at = utcnow()
    a.reviewed_by = account.id
    # Auto-reject any other pending applications this applicant has elsewhere.
    for other in db.scalars(
        select(GuildApplication).where(
            GuildApplication.account_id == a.account_id,
            GuildApplication.id != a.id,
            GuildApplication.status == GuildApplicationStatus.PENDING,
        )
    ):
        other.status = GuildApplicationStatus.REJECTED
        other.reviewed_at = utcnow()
    db.commit()
    return _detail(db, a.guild_id)  # type: ignore[return-value]


@router.post("/applications/{application_id}/reject", response_model=GuildApplicationOut)
def reject_application(
    application_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildApplicationOut:
    a = _load_app_for_review(db, account, application_id)
    a.status = GuildApplicationStatus.REJECTED
    a.reviewed_at = utcnow()
    a.reviewed_by = account.id
    db.commit()
    db.refresh(a)
    return _app_out(db, a)


@router.delete("/applications/{application_id}", response_model=GuildApplicationOut)
def withdraw_application(
    application_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildApplicationOut:
    """Applicant withdraws their own pending application."""
    a = db.get(GuildApplication, application_id)
    if a is None or a.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "application not found")
    if a.status != GuildApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"application already {a.status}")
    a.status = GuildApplicationStatus.WITHDRAWN
    a.reviewed_at = utcnow()
    db.commit()
    db.refresh(a)
    return _app_out(db, a)


# --- Guild-initiated invites (the inverse of applications) -------------------
#
# Application = player asks to join, leader/officer reviews.
# Invite      = leader/officer asks a player to join, player reviews.
#
# Same PENDING/ACCEPTED/REJECTED/WITHDRAWN lifecycle. A player may have many
# pending invites at once; first accept wins and the rest auto-reject because
# they suddenly already have a guild membership.


def _name_or_gone(account: Account | None) -> str:
    if account is None:
        return "[gone]"
    return account.email.split("@")[0]


def _invite_out(db: Session, inv: GuildInvite) -> GuildInviteOut:
    g = db.get(Guild, inv.guild_id)
    invitee = db.get(Account, inv.account_id)
    inviter = db.get(Account, inv.inviter_id) if inv.inviter_id else None
    return GuildInviteOut(
        id=inv.id,
        guild_id=inv.guild_id,
        guild_name=g.name if g else "[deleted]",
        guild_tag=g.tag if g else "",
        account_id=inv.account_id,
        invitee_name=_name_or_gone(invitee),
        inviter_id=inv.inviter_id,
        inviter_name=_name_or_gone(inviter),
        status=str(inv.status),
        message=inv.message,
        created_at=inv.created_at,
        decided_at=inv.decided_at,
    )


def _require_officer(m: GuildMember) -> None:
    if m.role not in (GuildRole.LEADER, GuildRole.OFFICER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "leaders/officers only")


@router.post(
    "/{guild_id}/invite/{account_id}",
    response_model=GuildInviteOut,
    status_code=status.HTTP_201_CREATED,
)
def invite_player(
    guild_id: int,
    account_id: int,
    body: GuildInviteIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildInviteOut:
    """Leader/officer extends an invite to a specific player."""
    membership = _require_membership(db, account, guild_id)
    _require_officer(membership)
    target = db.get(Account, account_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "player not found")
    if target.is_banned:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot invite a banned account")
    if target.id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "you're already in this guild")
    # Reject if target is already in any guild — they need to /leave first.
    if db.get(GuildMember, target.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "player already belongs to a guild")
    if _member_count(db, guild_id) >= MAX_GUILD_SIZE:
        raise HTTPException(status.HTTP_409_CONFLICT, "guild is full")
    # Avoid duplicate pending invites from the same guild.
    existing = db.scalar(
        select(GuildInvite).where(
            GuildInvite.account_id == target.id,
            GuildInvite.guild_id == guild_id,
            GuildInvite.status == GuildApplicationStatus.PENDING,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "an invite is already pending for this player")
    inv = GuildInvite(
        account_id=target.id,
        guild_id=guild_id,
        inviter_id=account.id,
        message=body.message.strip(),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return _invite_out(db, inv)


@router.get("/{guild_id}/invites", response_model=list[GuildInviteOut])
def list_outgoing_invites(
    guild_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    include_decided: bool = False,
) -> list[GuildInviteOut]:
    """Officers/leader see invites their guild has sent. Pending only by default."""
    membership = _require_membership(db, account, guild_id)
    _require_officer(membership)
    stmt = select(GuildInvite).where(GuildInvite.guild_id == guild_id)
    if not include_decided:
        stmt = stmt.where(GuildInvite.status == GuildApplicationStatus.PENDING)
    stmt = stmt.order_by(GuildInvite.created_at.desc()).limit(200)
    return [_invite_out(db, inv) for inv in db.scalars(stmt)]


@router.get("/invites/mine", response_model=list[GuildInviteOut])
def list_my_invites(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[GuildInviteOut]:
    """All invites addressed to the caller, newest first, capped per call."""
    limit = max(1, min(200, limit))
    rows = db.scalars(
        select(GuildInvite)
        .where(GuildInvite.account_id == account.id)
        .order_by(GuildInvite.created_at.desc())
        .limit(limit)
    )
    return [_invite_out(db, inv) for inv in rows]


def _load_invite_for_invitee(db: Session, account: Account, invite_id: int) -> GuildInvite:
    inv = db.get(GuildInvite, invite_id)
    if inv is None or inv.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invite not found")
    if inv.status != GuildApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"invite already {inv.status}")
    return inv


@router.post("/invites/{invite_id}/accept", response_model=GuildDetailOut)
def accept_invite(
    invite_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildDetailOut:
    inv = _load_invite_for_invitee(db, account, invite_id)
    if db.get(GuildMember, account.id) is not None:
        # Player joined another guild between the invite and accept — auto-reject.
        inv.status = GuildApplicationStatus.REJECTED
        inv.decided_at = utcnow()
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "you're already in a guild")
    if _member_count(db, inv.guild_id) >= MAX_GUILD_SIZE:
        raise HTTPException(status.HTTP_409_CONFLICT, "guild is full")
    db.add(GuildMember(account_id=account.id, guild_id=inv.guild_id, role=GuildRole.MEMBER))
    _update_guild_achievement(db, inv.guild_id, "members_joined", 1)
    inv.status = GuildApplicationStatus.ACCEPTED
    inv.decided_at = utcnow()
    # Auto-reject all other pending invites this player has — they now have a guild.
    for other in db.scalars(
        select(GuildInvite).where(
            GuildInvite.account_id == account.id,
            GuildInvite.id != inv.id,
            GuildInvite.status == GuildApplicationStatus.PENDING,
        )
    ):
        other.status = GuildApplicationStatus.REJECTED
        other.decided_at = utcnow()
    db.commit()
    return _detail(db, inv.guild_id)  # type: ignore[return-value]


@router.post("/invites/{invite_id}/reject", response_model=GuildInviteOut)
def reject_invite(
    invite_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildInviteOut:
    inv = _load_invite_for_invitee(db, account, invite_id)
    inv.status = GuildApplicationStatus.REJECTED
    inv.decided_at = utcnow()
    db.commit()
    db.refresh(inv)
    return _invite_out(db, inv)


@router.delete("/invites/{invite_id}", response_model=GuildInviteOut)
def cancel_invite(
    invite_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildInviteOut:
    """Leader/officer cancels a still-pending invite they (or another officer) sent.
    Rejected/accepted invites can't be 'cancelled' — they're already terminal."""
    inv = db.get(GuildInvite, invite_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invite not found")
    membership = db.get(GuildMember, account.id)
    if membership is None or membership.guild_id != inv.guild_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this guild")
    _require_officer(membership)
    if inv.status != GuildApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"invite already {inv.status}")
    inv.status = GuildApplicationStatus.WITHDRAWN
    inv.decided_at = utcnow()
    db.commit()
    db.refresh(inv)
    return _invite_out(db, inv)


# --- Guild achievements -------------------------------------------------------


def _build_achievement_out(
    db: Session, guild_id: int, ach: GuildAchievement,
) -> GuildAchievementOut:
    progress = db.scalar(
        select(GuildAchievementProgress).where(
            GuildAchievementProgress.guild_id == guild_id,
            GuildAchievementProgress.achievement_code == ach.code,
        )
    )
    current = progress.current_value if progress else 0
    return GuildAchievementOut(
        code=ach.code,
        name=ach.name,
        description=ach.description,
        category=ach.category,
        metric=ach.metric,
        target_value=ach.target_value,
        reward_gems=ach.reward_gems,
        reward_coins=ach.reward_coins,
        current_value=current,
        completed=progress.completed_at is not None if progress else False,
        reward_claimed=progress.reward_claimed_at is not None if progress else False,
    )


@router.get("/{guild_id}/achievements", response_model=GuildAchievementsResponse)
def list_guild_achievements(
    guild_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> GuildAchievementsResponse:
    """Public — no auth required. Returns all achievement definitions with per-guild progress."""
    if db.get(Guild, guild_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guild not found")
    definitions = db.scalars(select(GuildAchievement).order_by(GuildAchievement.id)).all()
    return GuildAchievementsResponse(
        achievements=[_build_achievement_out(db, guild_id, a) for a in definitions]
    )


@router.post(
    "/{guild_id}/achievements/{code}/claim",
    response_model=GuildAchievementOut,
    status_code=status.HTTP_200_OK,
)
def claim_guild_achievement(
    guild_id: int,
    code: str,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildAchievementOut:
    """Leader/officer claims the reward for a completed achievement. Idempotent."""
    m = _require_membership(db, account, guild_id)
    _require_officer(m)

    ach = db.scalar(select(GuildAchievement).where(GuildAchievement.code == code))
    if ach is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "achievement not found")

    progress = db.scalar(
        select(GuildAchievementProgress).where(
            GuildAchievementProgress.guild_id == guild_id,
            GuildAchievementProgress.achievement_code == code,
        )
    )
    if progress is None or progress.completed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "achievement not yet completed")
    if progress.reward_claimed_at is not None:
        # Idempotent: already claimed, just return the current state.
        return _build_achievement_out(db, guild_id, ach)

    # Grant rewards to the current guild leader (not created_by, which may be stale
    # after a leadership transfer).
    leader_row = db.scalar(
        select(GuildMember).where(
            GuildMember.guild_id == guild_id,
            GuildMember.role == GuildRole.LEADER,
        )
    )
    if leader_row is not None:
        leader_account = db.get(Account, leader_row.account_id)
        if leader_account is not None:
            leader_account.gems += ach.reward_gems
            leader_account.coins += ach.reward_coins

    progress.reward_claimed_at = utcnow()
    db.commit()
    return _build_achievement_out(db, guild_id, ach)
