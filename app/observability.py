"""Metrics, request-ID plumbing, and JSON log formatter.

- Prometheus counters/histogram are defined module-level so they're a singleton.
- `request_id_var` is a contextvar so log records can pick it up via a filter.
- `configure_logging()` is idempotent and switches formatter based on settings.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# --- Metrics -----------------------------------------------------------------

REQUESTS_TOTAL = Counter(
    "requests_total",
    "Total HTTP requests handled.",
    labelnames=("method", "path", "status"),
)
BATTLES_TOTAL = Counter("battles_total", "Total battle resolutions.")
SUMMONS_TOTAL = Counter("summons_total", "Total gacha pulls (x1 or x10 — counts pulls, not calls).")
REQUEST_DURATION = Histogram(
    "request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("method", "path"),
)


def metrics_response() -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


# --- Request ID --------------------------------------------------------------

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Honour incoming X-Request-ID (if sane) else generate one. Echo on response."""

    _HEADER = "x-request-id"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(self._HEADER, "").strip()
        # Reject absurdly long client-supplied values so we don't log unbounded junk.
        rid = incoming if 0 < len(incoming) <= 128 else uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


# --- Metrics middleware ------------------------------------------------------


class MetricsMiddleware(BaseHTTPMiddleware):
    """Count every request + observe duration. Also bumps battles/summons totals by path."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        # Don't self-observe the metrics endpoint.
        if path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            label_path = _normalize_path(path)
            REQUESTS_TOTAL.labels(
                method=request.method, path=label_path, status=str(status_code)
            ).inc()
            REQUEST_DURATION.labels(method=request.method, path=label_path).observe(duration)
            if status_code < 400:
                if label_path == "/battles" and request.method == "POST":
                    BATTLES_TOTAL.inc()
                elif label_path in ("/summon/x1", "/summon/x10") and request.method == "POST":
                    SUMMONS_TOTAL.inc(10 if label_path.endswith("x10") else 1)


def _normalize_path(path: str) -> str:
    """Collapse numeric IDs into :id so we don't blow up the label cardinality."""
    parts = path.split("/")
    for i, p in enumerate(parts):
        if p.isdigit():
            parts[i] = ":id"
    return "/".join(parts) or "/"


# --- Logging -----------------------------------------------------------------


class _RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 — logging contract
        record.request_id = request_id_var.get()
        return True


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(json_logs: bool) -> None:
    """(Re)configure root handlers. Safe to call multiple times."""
    root = logging.getLogger()
    # Strip prior handlers so uvicorn's dev basicConfig doesn't double-log.
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIDFilter())
    if json_logs:
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)s %(levelname)s [rid=%(request_id)s] %(message)s"
            )
        )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
