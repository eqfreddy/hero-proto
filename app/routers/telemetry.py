"""Lightweight telemetry sink — frontend perf metrics flow to PostHog.

Single endpoint: POST /telemetry/event. Accepts a metric name + numeric
value + optional metadata. Forwards to the analytics wrapper which
no-ops when PostHog isn't configured, so this is safe to call from
any environment (dev / test / prod).

The frontend uses navigator.sendBeacon to fire metrics from
beforeunload-able contexts (lazy-mounted Battle3DScene tear-down,
mount completion, etc.) without blocking the UI thread.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import analytics
from app.db import get_db
from app.deps import get_current_account
from app.models import Account

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryEventIn(BaseModel):
    # Bounded so the endpoint can't be abused as a free-form text sink.
    name: str = Field(min_length=1, max_length=80)
    value: float | None = None
    # Optional small key/value bag for context (e.g. archetype, theme).
    # Values stringified server-side before forwarding to analytics.
    meta: dict[str, str | int | float | bool] | None = None


@router.post("/event", status_code=status.HTTP_204_NO_CONTENT)
def record_event(
    body: TelemetryEventIn,
    account: Annotated[Account, Depends(get_current_account)],
    _db: Annotated[Session, Depends(get_db)],
) -> None:
    props: dict[str, object] = {}
    if body.value is not None:
        props["value"] = body.value
    if body.meta:
        # Cap to 12 keys so a misconfigured client can't explode props.
        for k, v in list(body.meta.items())[:12]:
            props[str(k)[:40]] = v
    analytics.track(body.name, account.id, props)
    return None
