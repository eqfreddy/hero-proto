"""Phase 2 follow-up — friends anti-spam hardening.

Captured in the post-shipment design notes as a launch-readiness
concern. Per-minute caps already shipped earlier; this batch adds
per-day caps that catch slow-burn spammers, plus a body-length cap.

Note on the test environment: `_enforce_account_bucket` short-circuits
when settings.environment == 'test' (the dashboard's CI shape relies on
this). So the rate-limit tests below patch settings.environment to
'dev' for the duration of the test to actually exercise the gate.
"""

from __future__ import annotations

import contextlib
import random
from unittest.mock import patch


@contextlib.contextmanager
def _rate_limits_active():
    """Temporarily flip settings off the test-env short-circuit + the
    `rate_limit_disabled` flag so the rate-limit dependencies actually
    run. Both checks live in `_enforce_account_bucket`; tripping either
    in the dev-default direction is enough to silence the gate, so we
    flip both."""
    from app.config import settings
    original_env = settings.environment
    original_disabled = settings.rate_limit_disabled
    settings.environment = "dev"
    settings.rate_limit_disabled = False
    try:
        yield
    finally:
        settings.environment = original_env
        settings.rate_limit_disabled = original_disabled


def _register(client) -> tuple[dict, int, str]:
    email = f"spam+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid, email


def test_dm_body_length_capped_at_1500_chars(client) -> None:
    """A 1501-char body should be rejected 422 by Pydantic before
    hitting the rate limiter."""
    sender_hdr, _, _ = _register(client)
    recipient_hdr, recipient_id, _ = _register(client)

    long_body = "x" * 1501
    r = client.post(
        f"/dm/with/{recipient_id}",
        json={"body": long_body},
        headers=sender_hdr,
    )
    assert r.status_code == 422
    # Within-cap message goes through.
    r2 = client.post(
        f"/dm/with/{recipient_id}",
        json={"body": "x" * 1500},
        headers=sender_hdr,
    )
    assert r2.status_code == 201, r2.text


def test_friend_request_per_minute_still_enforced(client) -> None:
    """Per-minute cap is the existing layer — verify it still fires
    when the rate-limit short-circuit is disabled."""
    from app.config import settings
    from app import deps as deps_module
    from app.middleware import TokenBucket

    sender_hdr, _, _ = _register(client)

    # Pre-register the targets first (registration is free; the rate-
    # limit gate only enforces on /friends/request itself).
    cap = settings.friend_request_per_minute_per_account
    targets = []
    for _ in range(cap + 1):
        _, tid, email = _register(client)
        targets.append((tid, email))

    # Use a fresh TokenBucket so we don't see leftover hits from earlier
    # tests in the session.
    fresh_minute = TokenBucket(limit_per_minute=cap, window_seconds=60)
    fresh_daily = TokenBucket(
        limit_per_minute=settings.friend_request_per_day_per_account,
        window_seconds=86400,
    )
    statuses = []
    with _rate_limits_active(), \
         patch.object(deps_module, "_friend_request_bucket", fresh_minute), \
         patch.object(deps_module, "_friend_request_daily_bucket", fresh_daily):
        for tid, email in targets:
            prefix = email.split("@")[0]
            statuses.append(client.post(
                "/friends/request",
                json={"email_prefix": prefix},
                headers=sender_hdr,
            ).status_code)

    # First N hit 201; the N+1th hits the per-minute gate.
    assert statuses[:cap].count(201) == cap, statuses
    assert statuses[cap] == 429, statuses[cap]


def test_friend_request_daily_cap_kicks_in_when_per_minute_passes(client) -> None:
    """Patch the per-minute bucket to always allow, then drive a small
    daily counter past its cap. Per-day rejection should surface a 429."""
    from app import deps as deps_module
    from app.middleware import TokenBucket

    sender_hdr, _, _ = _register(client)

    # Pre-create targets so registration noise doesn't interleave with
    # the spam loop.
    targets = []
    for _ in range(5):
        _, tid, email = _register(client)
        targets.append((tid, email))

    class _AlwaysAllow:
        def allow(self, key, now): return True
    small_daily = TokenBucket(limit_per_minute=3, window_seconds=86400)
    with _rate_limits_active(), \
         patch.object(deps_module, "_friend_request_bucket", _AlwaysAllow()), \
         patch.object(deps_module, "_friend_request_daily_bucket", small_daily):
        statuses = []
        for tid, email in targets:
            prefix = email.split("@")[0]
            statuses.append(client.post(
                "/friends/request",
                json={"email_prefix": prefix},
                headers=sender_hdr,
            ).status_code)

    successes = sum(1 for s in statuses if s == 201)
    rejections = sum(1 for s in statuses if s == 429)
    assert successes == 3, (successes, statuses)
    assert rejections == 2, (rejections, statuses)


def test_dm_daily_cap_rejects_with_429(client) -> None:
    """Same shape as the friend-request daily-cap test: per-minute
    bypassed via patch, daily bucket shrunk to 3, drive 5 requests."""
    from app import deps as deps_module
    from app.middleware import TokenBucket

    sender_hdr, _, _ = _register(client)
    _, recipient_id, _ = _register(client)

    class _AlwaysAllow:
        def allow(self, key, now): return True
    small_daily = TokenBucket(limit_per_minute=3, window_seconds=86400)
    with _rate_limits_active(), \
         patch.object(deps_module, "_direct_message_bucket", _AlwaysAllow()), \
         patch.object(deps_module, "_direct_message_daily_bucket", small_daily):
        statuses = []
        for i in range(5):
            statuses.append(client.post(
                f"/dm/with/{recipient_id}",
                json={"body": f"hi #{i}"},
                headers=sender_hdr,
            ).status_code)

    successes = sum(1 for s in statuses if s == 201)
    rejections = sum(1 for s in statuses if s == 429)
    assert successes == 3, (successes, statuses)
    assert rejections == 2, (rejections, statuses)
