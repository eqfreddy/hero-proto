from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.models import (
    Account,
    Guild,
    GuildMember,
    GuildMessage,
    GuildRole,
)
from app.schemas import (
    GuildCreateIn,
    GuildDetailOut,
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
    db.commit()
    db.refresh(guild)
    return _guild_out(db, guild)


@router.get("", response_model=list[GuildOut])
def list_guilds(db: Annotated[Session, Depends(get_db)]) -> list[GuildOut]:
    return [_guild_out(db, g) for g in db.scalars(select(Guild).order_by(Guild.id))]


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
) -> list[GuildMessageOut]:
    _require_membership(db, account, guild_id)
    rows = db.execute(
        select(GuildMessage.id, GuildMessage.guild_id, GuildMessage.author_id, Account.email, GuildMessage.body, GuildMessage.created_at)
        .outerjoin(Account, Account.id == GuildMessage.author_id)
        .where(GuildMessage.guild_id == guild_id)
        .order_by(GuildMessage.created_at.desc())
        .limit(50)
    )
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


@router.post("/{guild_id}/messages", response_model=GuildMessageOut, status_code=status.HTTP_201_CREATED)
def post_message(
    guild_id: int,
    body: GuildMessageIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> GuildMessageOut:
    _require_membership(db, account, guild_id)
    msg = GuildMessage(guild_id=guild_id, author_id=account.id, body=body.body.strip())
    db.add(msg)
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
