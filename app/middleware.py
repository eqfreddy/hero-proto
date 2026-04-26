"""Rate-limit + request-log middleware.

Rate limiting has two backends:
  - memory: per-process sliding window (fine for single-instance alpha).
  - redis:  shared sliding window via Redis sorted sets (for horizontal scale).

Select via HEROPROTO_RATE_LIMIT_BACKEND=memory|redis + HEROPROTO_REDIS_URL.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Callable, Protocol

import redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("http")

_WINDOW_SECONDS = 60.0


class RateBucket(Protocol):
    """Anything with allow(key, now) is a rate-limit backend."""

    def allow(self, key: str, now: float) -> bool: ...


class TokenBucket:
    """Per-process sliding window. O(hits) memory per key; acceptable for
    small instances, breaks under horizontal scaling (each replica has its
    own counter — the effective limit is N × configured)."""

    def __init__(self, limit_per_minute: int, *, window_seconds: int = _WINDOW_SECONDS) -> None:
        # Phase 2 follow-up: window_seconds defaults to 60 so all existing
        # callsites stay per-minute. Daily caps pass window_seconds=86400.
        # The kwarg name `limit_per_minute` is kept for back-compat with
        # callers that pre-date the windowing change; despite the name,
        # the integer is just a count-per-window once window_seconds is
        # overridden.
        self.limit = limit_per_minute
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float) -> bool:
        q = self.hits[key]
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class RedisTokenBucket:
    """Shared sliding window via Redis sorted sets.

    For each request we:
      ZREMRANGEBYSCORE  — evict timestamps older than (now - window)
      ZCARD             — count what remains
      If under limit: ZADD the current timestamp + EXPIRE for TTL-based cleanup
      Otherwise reject.

    We use a pipeline so all ops are round-tripped once per request.
    Idempotency under failure isn't a concern here — a dropped request just
    means the next one has a slightly stale count, which is fine for a
    bucket.
    """

    def __init__(self, client: redis.Redis, limit_per_minute: int, namespace: str, *, window_seconds: int = _WINDOW_SECONDS) -> None:
        self.client = client
        self.limit = limit_per_minute
        self.window = window_seconds
        self.namespace = namespace

    def _key(self, key: str) -> str:
        return f"hp:rl:{self.namespace}:{key}"

    def allow(self, key: str, now: float) -> bool:
        redis_key = self._key(key)
        cutoff = now - self.window
        # Eviction + count is read-only of state we're about to mutate, so do
        # them atomically via pipeline. member=score to keep members unique.
        try:
            pipe = self.client.pipeline()
            pipe.zremrangebyscore(redis_key, "-inf", cutoff)
            pipe.zcard(redis_key)
            _evicted, count = pipe.execute()
        except redis.RedisError:
            # Open-fail: if Redis is unreachable, don't lock users out. Log + allow.
            log.exception("redis rate-limit check failed; permitting request")
            return True

        if count >= self.limit:
            return False

        try:
            pipe = self.client.pipeline()
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, int(self.window) + 1)
            pipe.execute()
        except redis.RedisError:
            log.exception("redis rate-limit record failed")
        return True


def build_buckets(
    auth_rate_per_minute: int,
    general_rate_per_minute: int,
    backend: str,
    redis_url: str,
) -> tuple[RateBucket, RateBucket]:
    """Factory. Callable from tests with a mocked redis client — inject via
    Redis.from_url-replacing patches (see tests/test_rate_limit_redis.py)."""
    if backend == "redis":
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        # Touch the connection so misconfig surfaces at startup instead of
        # first-request. Open-fail would silently allow everything past.
        client.ping()
        return (
            RedisTokenBucket(client, auth_rate_per_minute, namespace="auth"),
            RedisTokenBucket(client, general_rate_per_minute, namespace="general"),
        )
    return (
        TokenBucket(auth_rate_per_minute),
        TokenBucket(general_rate_per_minute),
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        auth_rate_per_minute: int,
        general_rate_per_minute: int,
        backend: str = "memory",
        redis_url: str = "",
        trust_forwarded_for: bool = False,
    ) -> None:
        super().__init__(app)
        self.trust_forwarded_for = trust_forwarded_for
        self.auth_bucket, self.general_bucket = build_buckets(
            auth_rate_per_minute, general_rate_per_minute, backend, redis_url,
        )

    def _client_key(self, request: Request) -> str:
        # X-Forwarded-For is only consulted behind a proxy that strips it on
        # ingress — otherwise clients spoof their per-IP rate-limit key.
        if self.trust_forwarded_for:
            xff = request.headers.get("x-forwarded-for")
            if xff:
                return xff.split(",")[0].strip() or "unknown"
        if request.client is None:
            return "unknown"
        return request.client.host

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/healthz":
            return await call_next(request)
        key = self._client_key(request)
        now = time.monotonic()
        is_auth = request.url.path.startswith("/auth/")
        bucket = self.auth_bucket if is_auth else self.general_bucket
        if not bucket.allow(key, now):
            retry = 60
            return JSONResponse(
                {"detail": "rate limit exceeded — slow down"},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        return await call_next(request)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Structured-ish request log: method path status duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            log.exception("%s %s → 500 in %.1fms", request.method, request.url.path, duration_ms)
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        # Lean log: GET paths with 2xx at INFO; 4xx at INFO; 5xx at WARNING (unreachable — caught above).
        level = logging.INFO if status < 400 else logging.WARNING
        log.log(
            level,
            "%s %s -> %d in %.1fms",
            request.method,
            request.url.path,
            status,
            duration_ms,
        )
        return response
