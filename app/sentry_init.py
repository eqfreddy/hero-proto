"""Sentry error reporting — optional, DSN-gated.

init_sentry() is called once at application boot. With an empty DSN (the
default), Sentry stays uninitialized and zero runtime overhead happens. In
prod, set HEROPROTO_SENTRY_DSN to the project DSN.

We filter out FastAPI's HTTPException (4xx) events — those are expected
application-level rejections (invalid credentials, unknown resource, rate
limited) and reporting them drowns the actually-surprising 500s. 5xx and
non-HTTP exceptions still ship.

Request correlation: our RequestIDMiddleware stuffs a request_id contextvar
on every request; the before_send hook copies it into Sentry's tags so a
Sentry event can be stitched to its log line and metrics bucket.
"""

from __future__ import annotations

import logging
from typing import Any

import sentry_sdk
from fastapi import HTTPException
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import settings

log = logging.getLogger("sentry")

_initialized = False


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Filter + enrich events on the way to Sentry. Returns None to drop."""
    # Drop expected 4xx HTTPExceptions.
    exc_info = hint.get("exc_info") if hint else None
    if exc_info:
        exc = exc_info[1]
        if isinstance(exc, HTTPException) and 400 <= exc.status_code < 500:
            return None

    # Tag with the request id from our contextvar so we can cross-reference logs.
    try:
        from app.observability import request_id_var
        rid = request_id_var.get("-")
        if rid and rid != "-":
            event.setdefault("tags", {})["request_id"] = rid
    except Exception:
        pass  # sentry should never break because our tagger did

    return event


def init_sentry() -> bool:
    """Idempotent init. Returns True if Sentry was activated this call, False if
    skipped (empty DSN or already initialized)."""
    global _initialized
    if _initialized:
        return False
    if not settings.sentry_dsn:
        log.info("sentry disabled — HEROPROTO_SENTRY_DSN not set")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Only ship unhandled exceptions / manual captures, not every log line.
        # If we want log-line events later, add LoggingIntegration explicitly.
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        before_send=_before_send,
        # Don't capture request bodies by default — they often contain PII
        # (email, password, token). Send tags and status codes instead.
        send_default_pii=False,
        max_request_body_size="never",
    )
    _initialized = True
    log.info(
        "sentry initialized env=%s traces=%s",
        settings.sentry_environment or settings.environment,
        settings.sentry_traces_sample_rate,
    )
    return True
