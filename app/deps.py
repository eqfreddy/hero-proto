import time
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.middleware import TokenBucket
from app.models import Account, utcnow
from app.security import decode_token

# Per-account rate buckets, separate from the per-IP middleware buckets.
# Memory-only for now; per-account fanout is small enough that a single-process
# bucket is accurate for single-instance deploys. Horizontal scale can add a
# redis variant later if needed.
_battle_bucket = TokenBucket(settings.battle_per_minute_per_account)
_arena_bucket = TokenBucket(settings.arena_attack_per_minute_per_account)
_guild_msg_bucket = TokenBucket(settings.guild_message_per_minute_per_account)
_friend_request_bucket = TokenBucket(settings.friend_request_per_minute_per_account)
_direct_message_bucket = TokenBucket(settings.direct_message_per_minute_per_account)


def get_current_account(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Account:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        account_id, token_version = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "account not found")
    if token_version != account.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token revoked — please log in again")
    if account.is_banned:
        # Lazy auto-unban when a timed ban has elapsed — keeps the gate responsive
        # even if the worker hasn't ticked yet.
        if account.banned_until is not None and utcnow() >= account.banned_until:
            account.is_banned = False
            account.banned_reason = ""
            account.banned_until = None
            db.commit()
        else:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"account is banned: {account.banned_reason or 'no reason given'}",
            )
    return account


def get_current_admin(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    if not account.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return account


def _enforce_account_bucket(
    account: Account, bucket: TokenBucket, label: str,
) -> Account:
    if settings.rate_limit_disabled or settings.environment == "test":
        return account
    if not bucket.allow(f"acct:{account.id}", time.monotonic()):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"{label} rate limit exceeded for this account — slow down",
            headers={"Retry-After": "60"},
        )
    return account


def enforce_battle_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    """Per-account anti-hammer gate on /battles."""
    return _enforce_account_bucket(account, _battle_bucket, "battle")


def enforce_arena_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    """Per-account anti-hammer gate on /arena/attack."""
    return _enforce_account_bucket(account, _arena_bucket, "arena attack")


def enforce_guild_message_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    """Per-account anti-flood gate on /guilds/{id}/messages (POST)."""
    return _enforce_account_bucket(account, _guild_msg_bucket, "guild chat")


def enforce_friend_request_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    return _enforce_account_bucket(account, _friend_request_bucket, "friend request")


def enforce_direct_message_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    return _enforce_account_bucket(account, _direct_message_bucket, "direct message")
