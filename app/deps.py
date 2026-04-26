import logging
import time
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.middleware import RateBucket, RedisTokenBucket, TokenBucket
from app.models import Account, utcnow
from app.security import decode_token

_log = logging.getLogger("rate-limit")
_redis_client = None


def _get_redis_client():
    """Lazy-construct one Redis client for all per-action buckets. Open-fails:
    if Redis is unreachable, the per-bucket allow() also open-fails, so the
    request goes through with a logged error rather than locking users out."""
    global _redis_client
    if _redis_client is None:
        import redis as _redis  # local import keeps redis off the import path when unused

        _redis_client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _make_bucket(limit_per_minute: int, namespace: str) -> RateBucket:
    """Build a per-action bucket honouring settings.rate_limit_backend.

    Memory backend is per-process; under horizontal scale each replica has
    its own counter and the effective cap becomes N × limit. The Redis backend
    shares state across replicas — required for per-IP gates (the new
    guild-chat one) and recommended for per-account gates whenever > 1 worker
    is running.
    """
    if settings.rate_limit_backend == "redis":
        return RedisTokenBucket(_get_redis_client(), limit_per_minute, namespace=namespace)
    return TokenBucket(limit_per_minute)


# Per-action rate buckets, separate from the per-IP middleware buckets. Use the
# factory so they automatically pick up the configured backend (memory|redis).
_battle_bucket = _make_bucket(settings.battle_per_minute_per_account, "battle")
_arena_bucket = _make_bucket(settings.arena_attack_per_minute_per_account, "arena")
_guild_msg_bucket = _make_bucket(settings.guild_message_per_minute_per_account, "guild-msg")
_friend_request_bucket = _make_bucket(settings.friend_request_per_minute_per_account, "friend-req")
_direct_message_bucket = _make_bucket(settings.direct_message_per_minute_per_account, "dm")
_data_export_bucket = _make_bucket(settings.data_export_per_minute_per_account, "data-export")
# Per-IP layer that sits *underneath* per-account buckets. Used by guild chat
# to defend against rotating-account-on-one-IP spam. MUST be Redis-backed in
# horizontal-scale deploys — a per-IP gate that lives only inside one replica
# defeats its own purpose, since a botnet's traffic spreads across replicas.
_guild_msg_ip_bucket = _make_bucket(settings.guild_message_per_minute_per_ip, "guild-msg-ip")


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
    account: Account, bucket: RateBucket, label: str,
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
    """Per-account anti-flood gate on /guilds/{id}/messages (POST).

    The per-IP layer lives in `enforce_guild_message_ip_rate_limit` and is
    composed alongside this dep on the route. Splitting the two keeps the
    unit-test entry point Request-free and the dep stack readable.
    """
    return _enforce_account_bucket(account, _guild_msg_bucket, "guild chat")


def _request_ip(request: Request) -> str:
    """Resolve the request's client IP, honouring settings.trust_forwarded_for.

    When the flag is False (the safe default), we ignore X-Forwarded-For
    entirely so spoofed headers can't influence per-IP gates. When True,
    we read the leftmost entry — set this only behind a proxy that strips
    or replaces the header on ingress.
    """
    if settings.trust_forwarded_for:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def enforce_guild_message_ip_rate_limit(request: Request) -> None:
    """Per-IP anti-flood layer for guild chat — botnet defense.

    Stops a botnet on one IP from cycling through fresh accounts to bypass
    the per-account bucket. Cap is 3x the per-account rate so legit shared-IP
    cohorts (offices, NAT, dorms) hit the per-account gate first for whoever
    is actually misbehaving.
    """
    if settings.rate_limit_disabled or settings.environment == "test":
        return
    ip = _request_ip(request)
    if not _guild_msg_ip_bucket.allow(f"ip:{ip}", time.monotonic()):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "guild chat rate limit exceeded for this network — slow down",
            headers={"Retry-After": "60"},
        )


def enforce_data_export_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    """Per-account cap on /me/export. The query touches a dozen tables and the
    response can hit ~10MB; a tight cap keeps an authenticated attacker (or a
    stolen access token) from looping the endpoint to burn DB time."""
    return _enforce_account_bucket(account, _data_export_bucket, "data export")


def enforce_friend_request_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    return _enforce_account_bucket(account, _friend_request_bucket, "friend request")


def enforce_direct_message_rate_limit(
    account: Annotated[Account, Depends(get_current_account)],
) -> Account:
    return _enforce_account_bucket(account, _direct_message_bucket, "direct message")
