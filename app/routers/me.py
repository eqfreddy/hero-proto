from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.economy import compute_energy, load_cleared
from app.models import Account, Guild, GuildMember, GuildRole
from app.schemas import MeOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut)
def get_me(account: Annotated[Account, Depends(get_current_account)]) -> MeOut:
    return MeOut(
        id=account.id,
        email=account.email,
        gems=account.gems,
        coins=account.coins,
        shards=account.shards,
        access_cards=account.access_cards,
        energy=compute_energy(account),
        energy_cap=settings.energy_cap,
        pulls_since_epic=account.pulls_since_epic,
        stages_cleared=sorted(load_cleared(account)),
    )


class DeleteMeIn(BaseModel):
    confirm_email: EmailStr


@router.delete("", response_model=dict)
def delete_me(
    body: DeleteMeIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Irreversibly delete the caller's account and all related data (GDPR art. 17)."""
    if body.confirm_email.lower() != account.email.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm_email must match your account")

    # If this user is a guild leader, promote or disband cleanly before the cascade fires.
    membership = db.get(GuildMember, account.id)
    if membership is not None and membership.role == GuildRole.LEADER:
        from sqlalchemy import select

        successor = db.scalar(
            select(GuildMember)
            .where(
                GuildMember.guild_id == membership.guild_id,
                GuildMember.account_id != account.id,
            )
            .order_by(GuildMember.joined_at)
        )
        if successor is not None:
            successor.role = GuildRole.LEADER
        else:
            # Last member leaving — disband the guild so it doesn't orphan.
            g = db.get(Guild, membership.guild_id)
            if g is not None:
                db.delete(g)

    account_id = account.id
    account_email = account.email
    db.delete(account)
    db.commit()
    return {"deleted_account_id": account_id, "deleted_email": account_email}
