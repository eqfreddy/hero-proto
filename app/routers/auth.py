from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Account, utcnow
from app.schemas import LoginIn, RegisterIn, TokenOut
from app.security import hash_password, issue_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _maybe_promote_admin(account: Account) -> None:
    """Promote to admin if their email is in HEROPROTO_ADMIN_EMAILS. Idempotent."""
    if not account.is_admin and account.email.lower() in settings.admin_email_set():
        account.is_admin = True


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    if db.scalar(select(Account).where(Account.email == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    account = Account(
        email=body.email,
        password_hash=hash_password(body.password),
        shards=settings.starter_shards + settings.onboarding_bonus_shards,
        energy_stored=settings.starter_energy,
        energy_last_tick_at=utcnow(),
        coins=settings.starter_coins,
    )
    _maybe_promote_admin(account)
    db.add(account)
    db.commit()
    db.refresh(account)
    return TokenOut(access_token=issue_token(account.id, account.token_version))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    account = db.scalar(select(Account).where(Account.email == body.email))
    if account is None or not verify_password(body.password, account.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if account.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"account is banned: {account.banned_reason or 'no reason given'}",
        )
    _maybe_promote_admin(account)
    db.commit()
    return TokenOut(access_token=issue_token(account.id, account.token_version))
