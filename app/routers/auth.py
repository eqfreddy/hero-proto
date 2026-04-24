from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, EmailVerificationToken, utcnow
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
    db.flush()
    _row, refresh_raw = _issue_refresh_token(db, account)
    db.commit()
    db.refresh(account)
    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=refresh_raw,
    )


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
    _row, refresh_raw = _issue_refresh_token(db, account)
    db.commit()
    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=refresh_raw,
    )


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
        # Email the reset link via the configured sender. In non-prod we also
        # return the URL directly so clients can skip the mailbox step.
        from app.email_sender import get_sender as _get_sender
        full_url = f"{settings.public_base_url.rstrip('/')}/auth/reset-password?token={raw}"
        try:
            _get_sender().send(
                to_email=account.email,
                subject="hero-proto — password reset",
                body_text=(
                    f"Someone asked to reset the password for this account.\n\n"
                    f"Click this link within {PASSWORD_RESET_TTL_HOURS} hour(s) to pick a new password:\n"
                    f"  {full_url}\n\n"
                    f"If that wasn't you, you can safely ignore this message — "
                    f"your existing password keeps working."
                ),
            )
        except Exception:
            # Failures are non-fatal for the request (attacker enumeration resistance).
            _log.exception("password reset email delivery failed for %s", account.email)
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
    # _revoke_chain bumps token_version + revokes all live refresh tokens so no
    # previously-issued credential (access or refresh) is usable post-reset.
    _revoke_chain_for_account(db, account)
    token_row.used_at = utcnow()
    _new_refresh_row, refresh_raw = _issue_refresh_token(db, account)
    db.commit()
    # Issue a fresh access + refresh so the user is immediately signed in.
    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=refresh_raw,
    )


# --- Email verification ------------------------------------------------------

EMAIL_VERIFY_TTL_HOURS = 48  # longer than password reset because email delivery can be slow


def _issue_email_verification(db: Session, account: Account) -> tuple[EmailVerificationToken, str]:
    """Create a verification token for the account. Returns (row, raw_token)."""
    raw = secrets.token_urlsafe(32)
    row = EmailVerificationToken(
        account_id=account.id,
        token_hash=_hash_token(raw),
        expires_at=utcnow() + timedelta(hours=EMAIL_VERIFY_TTL_HOURS),
    )
    db.add(row)
    return row, raw


class VerifyRequestOut(BaseModel):
    status: str = "ok"
    already_verified: bool = False
    dev_verify_url: str | None = None


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class VerifyEmailOut(BaseModel):
    status: str = "verified"
    email: str


@router.post("/send-verification", response_model=VerifyRequestOut)
def send_verification(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> VerifyRequestOut:
    """Issue a fresh verification token for the currently-signed-in account.
    Idempotent if already verified — returns {already_verified: true} without
    creating a new token."""
    if account.email_verified:
        return VerifyRequestOut(already_verified=True)
    _row, raw = _issue_email_verification(db, account)
    db.commit()
    from app.email_sender import get_sender as _get_sender
    full_url = f"{settings.public_base_url.rstrip('/')}/auth/verify-email?token={raw}"
    try:
        _get_sender().send(
            to_email=account.email,
            subject="hero-proto — verify your email",
            body_text=(
                f"Confirm this email address belongs to you:\n\n"
                f"  {full_url}\n\n"
                f"Link expires in {EMAIL_VERIFY_TTL_HOURS} hours."
            ),
        )
    except Exception:
        _log.exception("email verification delivery failed for %s", account.email)
    dev_url = None
    if settings.environment.lower() != "prod":
        dev_url = f"/auth/verify-email?token={raw}"
        _log.info("email verification requested for %s — dev url: %s", account.email, dev_url)
    return VerifyRequestOut(dev_verify_url=dev_url)


@router.post("/verify-email", response_model=VerifyEmailOut)
def verify_email(
    body: VerifyEmailIn,
    db: Annotated[Session, Depends(get_db)],
) -> VerifyEmailOut:
    """Consume a verification token. Does not require authentication — the token
    itself proves the holder controls the inbox, which is the whole point."""
    row = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == _hash_token(body.token),
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or unknown verification token")
    if row.used_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "verification token already used")
    if row.expires_at <= utcnow():
        raise HTTPException(status.HTTP_410_GONE, "verification token has expired")

    account = db.get(Account, row.account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found")

    # Idempotent if already verified — consume the token but don't complain.
    now = utcnow()
    if not account.email_verified:
        account.email_verified = True
        account.email_verified_at = now
    row.used_at = now
    db.commit()
    return VerifyEmailOut(email=account.email)


# Import for the deps dependency so routers can require verification.
def get_current_account_verified_only(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    """Drop-in replacement for get_current_account that additionally requires
    email_verified. 403 if the caller hasn't verified yet."""
    if not account.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "this action requires a verified email",
        )
    return account


# --- Refresh tokens ----------------------------------------------------------

from app.models import RefreshToken


def _issue_refresh_token(db: Session, account: Account) -> tuple[RefreshToken, str]:
    """Persist a new RefreshToken row and return (row, raw_token)."""
    raw = secrets.token_urlsafe(40)
    row = RefreshToken(
        account_id=account.id,
        token_hash=_hash_token(raw),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(row)
    return row, raw


def _revoke_chain_for_account(db: Session, account: Account) -> None:
    """Invalidate everything for this account — called on refresh-token reuse
    detection (theft signal) or password reset. Bumps token_version so outstanding
    access tokens die, and revokes every live refresh row."""
    account.token_version = (account.token_version or 0) + 1
    for row in db.scalars(
        select(RefreshToken).where(
            RefreshToken.account_id == account.id,
            RefreshToken.revoked_at.is_(None),
        )
    ):
        row.revoked_at = utcnow()


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=128)


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=128)


class LogoutOut(BaseModel):
    revoked: bool


@router.post("/refresh", response_model=TokenOut)
def refresh(
    body: RefreshIn,
    db: Annotated[Session, Depends(get_db)],
) -> TokenOut:
    """Rotate the refresh token. Returns a fresh access token + a new refresh
    token; the presented token is marked replaced_by the new one. If the caller
    presents an already-rotated token (i.e. replaced_by_id is set), we treat it
    as theft and revoke the account's entire refresh chain."""
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(body.refresh_token))
    )
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")

    account = db.get(Account, row.account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account not found")

    now = utcnow()

    # Theft-detection: this token has already been rotated. Revoke everything.
    if row.replaced_by_id is not None:
        _revoke_chain_for_account(db, account)
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "refresh token reuse detected — all sessions revoked, please log in again",
        )

    if row.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token revoked")
    if row.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token expired")
    if account.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"account is banned: {account.banned_reason or 'no reason given'}",
        )

    # Rotate: issue a new token, mark old replaced.
    new_row, new_raw = _issue_refresh_token(db, account)
    db.flush()
    row.replaced_by_id = new_row.id
    row.revoked_at = now
    db.commit()

    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=new_raw,
    )


@router.post("/logout", response_model=LogoutOut)
def logout(
    body: LogoutIn,
    db: Annotated[Session, Depends(get_db)],
) -> LogoutOut:
    """Revoke a refresh token. Idempotent — an already-revoked or unknown token
    returns {revoked: false} with 200 (no sensitive info leaked)."""
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(body.refresh_token))
    )
    if row is None or row.revoked_at is not None:
        return LogoutOut(revoked=False)
    row.revoked_at = utcnow()
    db.commit()
    return LogoutOut(revoked=True)
