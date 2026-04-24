"""Rate-limit backends: memory TokenBucket and RedisTokenBucket (via fakeredis).

Doesn't drive the middleware end-to-end (the test env turns rate limits off —
see conftest + config). Exercises the bucket classes directly so the sliding
window math + Redis pipeline are covered independently.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from app.middleware import (
    RedisTokenBucket,
    TokenBucket,
    build_buckets,
)


# --- Memory bucket -----------------------------------------------------------


def test_memory_bucket_allows_under_limit() -> None:
    b = TokenBucket(limit_per_minute=5)
    now = 1000.0
    for i in range(5):
        assert b.allow("ip1", now + i) is True


def test_memory_bucket_rejects_over_limit() -> None:
    b = TokenBucket(limit_per_minute=3)
    now = 1000.0
    for _ in range(3):
        assert b.allow("ip1", now) is True
    # Fourth hit in same instant — rejected.
    assert b.allow("ip1", now) is False


def test_memory_bucket_slides_window() -> None:
    """After the 60-second window passes, old hits fall off."""
    b = TokenBucket(limit_per_minute=3)
    t0 = 1000.0
    # Saturate the bucket.
    for _ in range(3):
        b.allow("ip1", t0)
    assert b.allow("ip1", t0) is False
    # 61 seconds later — entire window has rolled off.
    assert b.allow("ip1", t0 + 61) is True


def test_memory_bucket_is_per_key() -> None:
    """Different keys (IPs) get independent buckets."""
    b = TokenBucket(limit_per_minute=2)
    now = 1000.0
    assert b.allow("ip1", now) is True
    assert b.allow("ip1", now) is True
    assert b.allow("ip1", now) is False
    # ip2 is fresh.
    assert b.allow("ip2", now) is True


# --- Redis bucket (via fakeredis) --------------------------------------------


@pytest.fixture
def redis_client():
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()


def test_redis_bucket_allows_under_limit(redis_client) -> None:
    b = RedisTokenBucket(redis_client, limit_per_minute=5, namespace="test")
    now = time.time()
    for i in range(5):
        assert b.allow("ip1", now + i * 0.001) is True


def test_redis_bucket_rejects_over_limit(redis_client) -> None:
    b = RedisTokenBucket(redis_client, limit_per_minute=3, namespace="test")
    now = time.time()
    # Each call needs a unique score, otherwise the sorted set dedupes.
    for i in range(3):
        assert b.allow("ip1", now + i * 0.001) is True
    assert b.allow("ip1", now + 0.004) is False


def test_redis_bucket_slides_window(redis_client) -> None:
    b = RedisTokenBucket(redis_client, limit_per_minute=3, namespace="test")
    t0 = time.time()
    for i in range(3):
        b.allow("ip1", t0 + i * 0.001)
    assert b.allow("ip1", t0 + 0.004) is False
    # Advance past the 60-second window — old entries evicted by ZREMRANGEBYSCORE.
    assert b.allow("ip1", t0 + 61.0) is True


def test_redis_bucket_isolated_per_key(redis_client) -> None:
    b = RedisTokenBucket(redis_client, limit_per_minute=2, namespace="test")
    now = time.time()
    b.allow("ip1", now)
    b.allow("ip1", now + 0.001)
    assert b.allow("ip1", now + 0.002) is False
    assert b.allow("ip2", now) is True


def test_redis_bucket_namespace_isolation(redis_client) -> None:
    """auth + general buckets must not share counters even if both use the
    same IP key — the namespace prefix separates them."""
    auth = RedisTokenBucket(redis_client, limit_per_minute=1, namespace="auth")
    general = RedisTokenBucket(redis_client, limit_per_minute=1, namespace="general")
    now = time.time()
    assert auth.allow("ip1", now) is True
    # auth is saturated...
    assert auth.allow("ip1", now + 0.001) is False
    # ...but general sees a fresh key.
    assert general.allow("ip1", now) is True


def test_redis_bucket_open_fails_on_redis_error(redis_client) -> None:
    """When Redis is unreachable, allow the request (open-fail) rather than
    locking users out. Logged-and-permitted is the prudent choice for an
    auxiliary check like rate limiting."""
    import redis as redis_module

    b = RedisTokenBucket(redis_client, limit_per_minute=1, namespace="test")
    # Sabotage the client so pipeline().execute() raises.
    with patch.object(redis_client, "pipeline") as mocked_pipeline:
        mocked = MagicMock()
        mocked.execute.side_effect = redis_module.RedisError("boom")
        mocked.zremrangebyscore.return_value = mocked
        mocked.zcard.return_value = mocked
        mocked_pipeline.return_value = mocked

        # Must allow despite the Redis failure.
        assert b.allow("ip1", time.time()) is True


# --- Factory -----------------------------------------------------------------


def test_build_buckets_memory_backend() -> None:
    auth, general = build_buckets(
        auth_rate_per_minute=10, general_rate_per_minute=100,
        backend="memory", redis_url="",
    )
    assert isinstance(auth, TokenBucket)
    assert isinstance(general, TokenBucket)
    assert auth.limit == 10
    assert general.limit == 100


def test_build_buckets_redis_backend(monkeypatch) -> None:
    """The 'redis' factory path pings the server at startup so misconfig
    fails loud — verified by patching from_url to return a fakeredis client."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "app.middleware.redis.Redis.from_url",
        lambda *_a, **_kw: fake,
    )
    auth, general = build_buckets(
        auth_rate_per_minute=10, general_rate_per_minute=100,
        backend="redis", redis_url="redis://localhost:6379/0",
    )
    assert isinstance(auth, RedisTokenBucket)
    assert isinstance(general, RedisTokenBucket)
    assert auth.namespace == "auth"
    assert general.namespace == "general"
