"""Sentry init gate + before_send filter.

We don't ship actual events to Sentry from tests — sentry_sdk.init() with a
real DSN isn't happening here. Instead we verify:
  - init_sentry() returns False with an empty DSN (default)
  - init_sentry() returns True when DSN is set (once — idempotent after)
  - _before_send drops expected 4xx HTTPExceptions
  - _before_send tags events with request_id when present
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import sentry_init as sentry_module
from app.sentry_init import _before_send, init_sentry


@pytest.fixture(autouse=True)
def _reset_init_flag():
    """Each test gets a clean _initialized state so init_sentry is re-runnable."""
    yield
    sentry_module._initialized = False


def test_init_skipped_with_empty_dsn(monkeypatch) -> None:
    from app.config import settings
    monkeypatch.setattr(settings, "sentry_dsn", "")
    assert init_sentry() is False


def test_init_runs_with_dsn(monkeypatch) -> None:
    from app.config import settings
    monkeypatch.setattr(settings, "sentry_dsn", "https://fake@sentry.test/123")

    with patch("sentry_sdk.init") as mock_init:
        assert init_sentry() is True
        mock_init.assert_called_once()
        kwargs = mock_init.call_args.kwargs
        assert kwargs["dsn"] == "https://fake@sentry.test/123"
        assert kwargs["send_default_pii"] is False
        assert kwargs["before_send"] is _before_send


def test_init_is_idempotent(monkeypatch) -> None:
    from app.config import settings
    monkeypatch.setattr(settings, "sentry_dsn", "https://fake@sentry.test/123")

    with patch("sentry_sdk.init") as mock_init:
        assert init_sentry() is True
        # Second call — no-ops.
        assert init_sentry() is False
        assert mock_init.call_count == 1


def test_before_send_drops_4xx_httpexceptions() -> None:
    """400/401/403/404/409/422 are expected — we don't pollute Sentry with them."""
    for status_code in (400, 401, 403, 404, 409, 410, 422, 429):
        event = {"message": f"test-{status_code}"}
        exc = HTTPException(status_code=status_code, detail="test")
        hint = {"exc_info": (type(exc), exc, None)}
        assert _before_send(event, hint) is None, f"should drop {status_code}"


def test_before_send_keeps_5xx_httpexceptions() -> None:
    event = {"message": "server error"}
    exc = HTTPException(status_code=500, detail="boom")
    hint = {"exc_info": (type(exc), exc, None)}
    result = _before_send(event, hint)
    assert result is event  # pass-through


def test_before_send_keeps_non_http_exceptions() -> None:
    event = {"message": "value error"}
    exc = ValueError("bad input")
    hint = {"exc_info": (type(exc), exc, None)}
    result = _before_send(event, hint)
    assert result is event


def test_before_send_tags_with_request_id() -> None:
    """When our request-id contextvar is set, copy it into event tags."""
    from app.observability import request_id_var

    event: dict = {"message": "test"}
    hint: dict = {}
    token = request_id_var.set("abc123")
    try:
        _before_send(event, hint)
    finally:
        request_id_var.reset(token)
    assert event.get("tags", {}).get("request_id") == "abc123"


def test_before_send_no_tag_when_request_id_default() -> None:
    """'-' is the default placeholder when no request context — shouldn't leak."""
    event: dict = {"message": "test"}
    hint: dict = {}
    _before_send(event, hint)
    assert "request_id" not in event.get("tags", {})
