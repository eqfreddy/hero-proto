"""Rate-limit + request-log middleware. In-memory only — fine for single-instance alpha."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("http")


class TokenBucket:
    """Simple sliding-window counter keyed by IP.

    Stores timestamps of the last N requests and rejects if window count > limit.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self.window = 60.0
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


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_rate_per_minute: int, general_rate_per_minute: int) -> None:
        super().__init__(app)
        self.auth_bucket = TokenBucket(auth_rate_per_minute)
        self.general_bucket = TokenBucket(general_rate_per_minute)

    def _client_key(self, request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
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
