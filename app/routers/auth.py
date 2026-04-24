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


# --- Password reset ----------------------------------------------------------

import hashlib
import logging
import secrets
from datetime import timedelta

from pydantic import BaseModel, EmailStr, Field

from app.models import PasswordResetToken

_log = logging.getLogger("auth.password_reset")

PASSWORD_RESET_TTL_HOURS = 1


def _hash_token(raw: str) -> str:
    """SHA-256 of the raw token. Stored hash prevents DB-leak impersonation."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)


class PasswordResetStartedOut(BaseModel):
    # We never leak whether the email exists — status is always the same shape.
    status: str = "ok"
    # In dev/test, also return the reset URL so clients can skip the email step.
    dev_reset_url: str | None = None


@router.post("/forgot-password", response_model=PasswordResetStartedOut)
def forgot_password(
    body: ForgotPasswordIn,
    db: Annotated[Session, Depends(get_db)],
) -> PasswordResetStartedOut:
    """Start a password reset. Returns 200 regardless of whether the email
    exists, so an attacker can't enumerate accounts by probing this endpoint.

    In dev/test environments the reset URL is returned in the response body
    for convenience (no email sender wired yet). In prod this field is always
    None and the URL goes through the email path — to be added later.
    """
    account = db.scalar(select(Account).where(Account.email == body.email))
    dev_url: str | None = None
    if account is not None:
        # Generate a long random token; store only the hash.
        raw = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            account_id=account.id,
            token_hash=_hash_token(raw),
            expires_at=utcnow() + timedelta(hours=PASSWORD_RESET_TTL_HOURS),
        ))
        db.commit()
        if settings.environment.lower() != "prod":
            dev_url = f"/auth/reset-password?token={raw}"
            _log.info("password reset requested for %s — dev url: %s", account.email, dev_url)
    return PasswordResetStartedOut(dev_reset_url=dev_url)


@router.post("/reset-password", response_model=TokenOut)
def reset_password(
    body: ResetPasswordIn,
    db: Annotated[Session, Depends(get_db)],
) -> TokenOut:
    """Consume a reset token and set a new password. Bumps token_version so any
    JWTs already out in the wild (stolen or otherwise) are invalidated immediately."""
    token_row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(body.token),
        )
    )
    if token_row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or unknown reset token")
    if token_row.used_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "reset token already used")
    if token_row.expires_at <= utcnow():
        raise HTTPException(status.HTTP_410_GONE, "reset token has expired")

    account = db.get(Account, token_row.account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")

    account.password_hash = hash_password(body.new_password)
    account.token_version = (account.token_version or 0) + 1  # revoke outstanding JWTs
    token_row.used_at = utcnow()
    db.commit()

    # Issue a fresh token so the user is immediately signed in after reset.
    return TokenOut(access_token=issue_token(account.id, account.token_version))
