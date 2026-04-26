"""PostHog product analytics — graceful no-op wrapper.

Wraps `posthog-python` so the rest of the codebase has one place to call
`track()` from, regardless of whether PostHog is configured. The 12 events
in the Phase 2 PRD (register, login, summon_*, stage_*, first_clear,
purchase_*, arena_attack, raid_attack, daily_bonus_claim) all flow through
here.

Behavior:
  - If `settings.posthog_api_key` is empty OR `settings.posthog_disabled`
    is True OR `settings.environment == "test"`, every `track()` call is a
    silent no-op. No client is created, no network traffic, no log noise.
  - Otherwise a single module-level `Posthog` client is lazy-initialized on
    first track() and reused. Events are queued + flushed on a background
    thread by the posthog-python client (default: 1Hz / 100-event batches).
  - `posthog` is an optional dep (extra `analytics-runtime`); if it's not
    installed, the wrapper falls back to no-op even with a key set, and
    logs a single warning so ops notices the misconfig without spamming.

Distinct ID convention: account_id stringified (e.g. "42"). Anonymous
events (the rare pre-account flows) use a session-level UUID, not the
PostHog default `$device_id`.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import settings

_log = logging.getLogger("analytics")

# Module-level state — guarded by _client_lock so concurrent first-track
# calls don't double-init.
_client: Any = None
_client_lock = threading.Lock()
_client_init_failed = False


def _build_client():
    """Lazy-init the Posthog client. Returns None if posthog-python isn't
    installed or already failed to import — callers treat None as 'no-op'."""
    global _client_init_failed
    if _client_init_failed:
        return None
    try:
        from posthog import Posthog  # type: ignore[import-not-found]
    except ImportError:
        _log.warning(
            "POSTHOG_API_KEY is set but posthog-python is not installed; "
            "analytics is disabled. Add it via `uv sync --extra analytics-runtime`."
        )
        _client_init_failed = True
        return None
    return Posthog(
        project_api_key=settings.posthog_api_key,
        host=settings.posthog_host,
    )


def _enabled() -> bool:
    if settings.posthog_disabled:
        return False
    if settings.environment == "test":
        return False
    if not settings.posthog_api_key:
        return False
    return True


def _get_client():
    """Return the shared client (lazy-init), or None if disabled/unconfigured."""
    global _client
    if not _enabled():
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        _client = _build_client()
        return _client


def track(event: str, account_id: int | None, properties: dict | None = None) -> None:
    """Fire a product-analytics event.

    `account_id` is the canonical distinct_id; anonymous flows pass None and
    we fall back to a placeholder. Properties are merged with always-on
    fields (env, request_id) so funnel queries can scope by environment.

    Errors are swallowed and logged — analytics failures must never propagate
    into the request path. The posthog client itself buffers + flushes async,
    so this call is essentially a queue.put().
    """
    client = _get_client()
    if client is None:
        return
    try:
        from app.observability import request_id_var
        rid = request_id_var.get()
    except Exception:
        rid = "-"
    distinct_id = str(account_id) if account_id is not None else "anonymous"
    payload = {
        "env": settings.environment,
        "request_id": rid,
        **(properties or {}),
    }
    try:
        client.capture(distinct_id=distinct_id, event=event, properties=payload)
    except Exception as exc:
        # PostHog network/serialization issues are operational noise — log
        # at warning level so they're visible but don't 500 the request.
        _log.warning("posthog.capture(%r) failed: %s", event, exc)


def shutdown() -> None:
    """Flush queued events on graceful shutdown. Called from the lifespan
    `finally` block so the last batch isn't lost when uvicorn exits."""
    global _client
    if _client is None:
        return
    try:
        _client.shutdown()
    except Exception as exc:
        _log.warning("posthog.shutdown() failed: %s", exc)


def _reset_for_tests() -> None:
    """Clear module-level state. Tests use this to swap in a mock client."""
    global _client, _client_init_failed
    _client = None
    _client_init_failed = False
