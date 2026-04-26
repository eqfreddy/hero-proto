from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, EmailVerificationToken, HeroInstance, HeroTemplate, Rarity, utcnow
from app.schemas import LoginIn, RegisterIn, TokenOut
from app.security import hash_password, issue_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _maybe_promote_admin(account: Account) -> None:
    """Promote to admin if their email is in HEROPROTO_ADMIN_EMAILS. Idempotent."""
    if not account.is_admin and account.email.lower() in settings.admin_email_set():
        account.is_admin = True


STARTER_TEAM_SIZE = 3


def _grant_starter_team(db: Session, account: Account) -> None:
    """Grant the player a 3-hero starter roster from the COMMON pool.

    Without this, a brand-new account has no heroes to field for the tutorial
    battle — the whole guided-first-session flow dead-ends at step 1. Keep
    the starter pool deliberately weak (COMMON only) so gacha pulls still
    feel like an upgrade.
    """
    import random as _random

    commons = list(db.scalars(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.COMMON)
    ))
    if not commons:
        # Degenerate content state; skip silently rather than 500 registration.
        return
    rng = _random.Random()
    # Pick with replacement so small COMMON pools still fill the team; dupes are
    # fine and actually useful for the ascension-fodder flow.
    picks = [rng.choice(commons) for _ in range(STARTER_TEAM_SIZE)]
    for tmpl in picks:
        db.add(HeroInstance(
            account_id=account.id,
            template_id=tmpl.id,
            level=1, xp=0,
        ))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterIn,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenOut:
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
    _grant_starter_team(db, account)
    _row, refresh_raw = _issue_refresh_token(db, account, request)
    db.commit()
    db.refresh(account)
    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=refresh_raw,
    )


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Password login. If the account has TOTP enabled, returns a short-lived
    challenge_token instead of a real access token — the client must follow up
    with POST /auth/2fa/verify using that token + the current TOTP code."""
    account = db.scalar(select(Account).where(Account.email == body.email))
    if account is None or not verify_password(body.password, account.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if account.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"account is banned: {account.banned_reason or 'no reason given'}",
        )
    _maybe_promote_admin(account)

    # TOTP-gated accounts get a challenge, not tokens.
    if account.totp_enabled:
        db.commit()
        return LoginChallengeOut(challenge_token=_issue_totp_challenge(account)).model_dump()

    _row, refresh_raw = _issue_refresh_token(db, account, request)
    db.commit()
    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=refresh_raw,
    ).model_dump()


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
        from app.email_render import render_password_reset
        from app.email_sender import get_sender as _get_sender
        # The reset link points at the HTML page (which then POSTs the token
        # to /auth/reset-password). Keep the API endpoint and the user-facing
        # page on different URLs so the latter can stay GET-friendly.
        full_url = f"{settings.public_base_url.rstrip('/')}/reset-password?token={raw}"
        try:
            subject, text_body, html_body = render_password_reset(
                reset_url=full_url, ttl_hours=PASSWORD_RESET_TTL_HOURS,
            )
            _get_sender().send(
                to_email=account.email,
                subject=subject,
                body_text=text_body,
                body_html=html_body,
            )
        except Exception:
            # Failures are non-fatal for the request (attacker enumeration resistance).
            _log.exception("password reset email delivery failed for %s", account.email)
        if settings.environment.lower() != "prod":
            dev_url = f"/reset-password?token={raw}"
            _log.info("password reset requested for %s — dev url: %s", account.email, dev_url)
    return PasswordResetStartedOut(dev_reset_url=dev_url)


@router.post("/reset-password", response_model=TokenOut)
def reset_password(
    body: ResetPasswordIn,
    request: Request,
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
    _new_refresh_row, refresh_raw = _issue_refresh_token(db, account, request)
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
    from app.email_render import render_verify_email
    from app.email_sender import get_sender as _get_sender
    full_url = f"{settings.public_base_url.rstrip('/')}/auth/verify-email?token={raw}"
    try:
        subject, text_body, html_body = render_verify_email(
            verify_url=full_url, ttl_hours=EMAIL_VERIFY_TTL_HOURS,
        )
        _get_sender().send(
            to_email=account.email,
            subject=subject,
            body_text=text_body,
            body_html=html_body,
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


def _client_ip(req: Request | None) -> str | None:
    if req is None:
        return None
    # X-Forwarded-For is only consulted when the deployment opts in via
    # settings.trust_forwarded_for — otherwise a client could spoof both the
    # per-IP rate-limit key AND the IP shown in their own session list.
    if settings.trust_forwarded_for:
        fwd = req.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()[:64] or None
    return req.client.host[:64] if req.client else None


def _client_ua(req: Request | None) -> str | None:
    if req is None:
        return None
    ua = req.headers.get("user-agent")
    return ua[:256] if ua else None


def _issue_refresh_token(
    db: Session,
    account: Account,
    request: Request | None = None,
) -> tuple[RefreshToken, str]:
    """Persist a new RefreshToken row and return (row, raw_token).

    Captures IP + user-agent at issue time when a Request is available, so
    the active-sessions list can show the user where each session came from.
    """
    raw = secrets.token_urlsafe(40)
    row = RefreshToken(
        account_id=account.id,
        token_hash=_hash_token(raw),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
        created_ip=_client_ip(request),
        user_agent=_client_ua(request),
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
    request: Request,
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
    row.last_used_at = now
    new_row, new_raw = _issue_refresh_token(db, account, request)
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


# --- TOTP 2FA ----------------------------------------------------------------

import pyotp
import jwt as _jwt
from app.models import TotpRecoveryCode

TOTP_ISSUER = "hero-proto"
TOTP_CHALLENGE_TTL_MINUTES = 5
RECOVERY_CODE_COUNT = 10
# Avoid ambiguous characters (0/O, 1/I/L). 4-4 formatted for readability.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _generate_recovery_code() -> str:
    """Returns a user-facing recovery code like 'ABCD-EFGH'."""
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _issue_recovery_codes(db: Session, account: Account) -> list[str]:
    """Create RECOVERY_CODE_COUNT fresh codes and persist their hashes.
    Caller is responsible for clearing any prior codes before calling this.
    Returns the plaintext codes (the only time they're available)."""
    plaintext = [_generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in plaintext:
        db.add(TotpRecoveryCode(
            account_id=account.id,
            code_hash=_hash_token(code),
        ))
    return plaintext


def _revoke_recovery_codes(db: Session, account: Account) -> None:
    """Delete all codes (used or unused) for the account. Called on disable
    or regenerate."""
    for row in db.scalars(
        select(TotpRecoveryCode).where(TotpRecoveryCode.account_id == account.id)
    ):
        db.delete(row)


def _count_unused_recovery_codes(db: Session, account_id: int) -> int:
    from sqlalchemy import func
    return db.scalar(
        select(func.count(TotpRecoveryCode.id)).where(
            TotpRecoveryCode.account_id == account_id,
            TotpRecoveryCode.used_at.is_(None),
        )
    ) or 0


def _try_consume_recovery_code(db: Session, account: Account, code: str) -> bool:
    """If `code` matches an unused recovery code for the account, mark it used
    and return True. Otherwise False. Accepts both 'ABCD-EFGH' and 'ABCDEFGH'
    forms for typing forgiveness."""
    normalized_candidates = [code.strip().upper()]
    # Allow the no-dash variant to match too.
    stripped = code.strip().upper().replace("-", "")
    if len(stripped) == 8:
        normalized_candidates.append(f"{stripped[:4]}-{stripped[4:]}")
    for candidate in normalized_candidates:
        row = db.scalar(
            select(TotpRecoveryCode).where(
                TotpRecoveryCode.account_id == account.id,
                TotpRecoveryCode.code_hash == _hash_token(candidate),
                TotpRecoveryCode.used_at.is_(None),
            )
        )
        if row is not None:
            row.used_at = utcnow()
            return True
    return False


class TotpEnrollOut(BaseModel):
    """Response from /auth/2fa/enroll. The client should render `otpauth_uri`
    as a QR code (or show `secret` for manual entry) so the user can add
    this account to an authenticator app."""
    secret: str
    otpauth_uri: str


class TotpCodeIn(BaseModel):
    # Accepts both a 6-8 digit TOTP and an 8-9 char recovery code (e.g. "ABCD-EFGH").
    code: str = Field(min_length=6, max_length=16)


class TotpStatusOut(BaseModel):
    enabled: bool
    recovery_codes_remaining: int = 0


class TotpConfirmOut(BaseModel):
    """Confirm response. recovery_codes is the plaintext list of 10 codes —
    returned ONCE, at enrollment. Clients must show these to the user and
    tell them to save them. Server only retains hashes."""
    enabled: bool
    recovery_codes: list[str]


class TotpRegenerateOut(BaseModel):
    recovery_codes: list[str]


class LoginChallengeOut(BaseModel):
    """Returned by /auth/login when the account has TOTP enabled. The client
    prompts for a TOTP code, then POSTs both `challenge_token` and the code
    to /auth/2fa/verify to receive the real access+refresh tokens."""
    status: str = "totp_required"
    challenge_token: str


class TotpVerifyIn(BaseModel):
    challenge_token: str = Field(min_length=16, max_length=512)
    # Same relaxed bounds as TotpCodeIn — supports TOTP digits + recovery codes.
    code: str = Field(min_length=6, max_length=16)


def _issue_totp_challenge(account: Account) -> str:
    """Short-lived JWT that authorizes a TOTP verification attempt. Kept
    stateless (no DB row) — only the signing secret and expiry gate it.
    Uses aware UTC datetime so .timestamp() reflects UTC epoch seconds, not
    local-time seconds (matching security.issue_token's convention)."""
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc)
    payload = {
        "sub": str(account.id),
        "typ": "totp_challenge",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=TOTP_CHALLENGE_TTL_MINUTES)).timestamp()),
    }
    return _jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def _decode_totp_challenge(token: str) -> int:
    """Returns account_id on success. Raises HTTPException with 401 on any
    signature/expiry/type problem."""
    try:
        payload = _jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except _jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid challenge: {exc}") from exc
    if payload.get("typ") != "totp_challenge":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong challenge type")
    return int(payload["sub"])


@router.post("/2fa/enroll", response_model=TotpEnrollOut)
def totp_enroll(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> TotpEnrollOut:
    """Generate a fresh secret and return the otpauth URI. Not yet enabled —
    the user must /2fa/confirm with a valid code before TOTP gates login."""
    if account.totp_enabled:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "2FA is already enabled — disable it first to re-enroll",
        )
    secret = pyotp.random_base32()
    account.totp_secret = secret
    account.totp_enabled = False  # stays off until confirmed
    db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=account.email, issuer_name=TOTP_ISSUER,
    )
    return TotpEnrollOut(secret=secret, otpauth_uri=uri)


@router.post("/2fa/confirm", response_model=TotpConfirmOut)
def totp_confirm(
    body: TotpCodeIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> TotpConfirmOut:
    """Verify the first code + flip totp_enabled. Issues 10 one-time recovery
    codes that are returned here and nowhere else — clients must display them
    prominently because the plaintext isn't retrievable later (only hashes are
    stored)."""
    if not account.totp_secret:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "no pending 2FA enrollment — call /auth/2fa/enroll first",
        )
    if account.totp_enabled:
        # Already enabled: idempotent, but don't re-issue recovery codes.
        return TotpConfirmOut(enabled=True, recovery_codes=[])
    if not pyotp.TOTP(account.totp_secret).verify(body.code, valid_window=1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid TOTP code")

    account.totp_enabled = True
    # Clear any stale codes from a prior aborted enrollment, then issue fresh.
    _revoke_recovery_codes(db, account)
    plaintext = _issue_recovery_codes(db, account)
    db.commit()
    return TotpConfirmOut(enabled=True, recovery_codes=plaintext)


@router.post("/2fa/disable", response_model=TotpStatusOut)
def totp_disable(
    body: TotpCodeIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> TotpStatusOut:
    """Turn off 2FA. Requires a current valid TOTP code OR a recovery code —
    both paths count as "holder controls a second factor". Clears the secret
    and revokes every recovery code so re-enrollment issues fresh ones."""
    if not account.totp_enabled:
        return TotpStatusOut(enabled=False, recovery_codes_remaining=0)
    code = body.code.strip()
    valid_totp = bool(account.totp_secret) and pyotp.TOTP(account.totp_secret).verify(code, valid_window=1)
    valid_recovery = False
    if not valid_totp:
        # Try recovery code fallback. Consumes the code on success.
        valid_recovery = _try_consume_recovery_code(db, account, code)
    if not (valid_totp or valid_recovery):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid TOTP or recovery code")
    account.totp_enabled = False
    account.totp_secret = ""
    _revoke_recovery_codes(db, account)
    db.commit()
    return TotpStatusOut(enabled=False, recovery_codes_remaining=0)


@router.post("/2fa/verify", response_model=TokenOut)
def totp_verify(
    body: TotpVerifyIn,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenOut:
    """Consume a login challenge + TOTP code OR recovery code, return the real
    access+refresh pair. Recovery codes are single-use — consumption on match."""
    account_id = _decode_totp_challenge(body.challenge_token)
    account = db.get(Account, account_id)
    if account is None or not account.totp_enabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account or 2FA state changed")
    if account.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"account is banned: {account.banned_reason or 'no reason given'}",
        )

    code = body.code.strip()
    valid_totp = pyotp.TOTP(account.totp_secret).verify(code, valid_window=1)
    valid_recovery = False
    if not valid_totp:
        valid_recovery = _try_consume_recovery_code(db, account, code)
    if not (valid_totp or valid_recovery):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid TOTP or recovery code")

    _row, refresh_raw = _issue_refresh_token(db, account, request)
    db.commit()
    return TokenOut(
        access_token=issue_token(account.id, account.token_version),
        refresh_token=refresh_raw,
    )


@router.post("/2fa/regenerate-codes", response_model=TotpRegenerateOut)
def totp_regenerate_codes(
    body: TotpCodeIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> TotpRegenerateOut:
    """Replace all existing recovery codes with a fresh set. Requires a current
    TOTP code (or existing recovery code) as authorization — same bar as disable."""
    if not account.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "2FA is not enabled")
    code = body.code.strip()
    valid_totp = bool(account.totp_secret) and pyotp.TOTP(account.totp_secret).verify(code, valid_window=1)
    valid_recovery = False
    if not valid_totp:
        valid_recovery = _try_consume_recovery_code(db, account, code)
    if not (valid_totp or valid_recovery):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid TOTP or recovery code")
    _revoke_recovery_codes(db, account)
    plaintext = _issue_recovery_codes(db, account)
    db.commit()
    return TotpRegenerateOut(recovery_codes=plaintext)


@router.get("/2fa/status", response_model=TotpStatusOut)
def totp_status(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> TotpStatusOut:
    remaining = _count_unused_recovery_codes(db, account.id) if account.totp_enabled else 0
    return TotpStatusOut(enabled=account.totp_enabled, recovery_codes_remaining=remaining)
