"""Event storefront surface — banner + bundle exposed on /events/active.

The Event tab is meant to be the landing page for a live event, but the
payload only carried quests + milestones (a pure free earn/spend loop). The
event JSON already defines an EVENT_BANNER (paid pull) and a shop bundle
(real money), buried in liveops/shop. These tests drive surfacing them so
the gold tab actually funnels to a pull and a purchase.
"""

from __future__ import annotations

import dataclasses
import random
from datetime import timedelta
from pathlib import Path

import pytest

from app import event_state
from app.event_state import EventSpec, load_event_spec
from app.models import utcnow

_MOTHERS_DAY = Path(__file__).resolve().parent.parent / "events" / "2026-05-10_mothers_day.json"


def test_load_event_spec_parses_banner_and_bundle() -> None:
    spec = load_event_spec(_MOTHERS_DAY)

    assert spec.banner is not None, "EVENT_BANNER liveop should parse into spec.banner"
    assert spec.banner["hero_template_code"] == "applecrumb"
    assert spec.banner["shard_cost"] == 8
    assert spec.banner["per_account_cap"] == 5

    assert spec.bundle is not None, "shop[0] should parse into spec.bundle"
    assert spec.bundle["sku"] == "mothers_day_2026_bouquet"
    assert spec.bundle["price_cents"] == 1199
    assert spec.bundle["contents"]["gems"] == 1200


def test_spec_without_banner_or_bundle_is_none() -> None:
    """A quest-only spec (no liveops banner, no shop) reports null, not a crash."""
    now = utcnow()
    spec = EventSpec(
        id="quest_only_2026",
        display_name="Quest Only",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=24),
        currency_name="Sparks",
        currency_emoji="⚡",
        drops={},
        quests=[],
        milestones=[],
    )
    assert spec.banner is None
    assert spec.bundle is None


@pytest.fixture
def active_mothers_day(monkeypatch):
    """Pin the real Mother's Day spec (which has a banner + bundle) as active,
    shifting its window to 'now' so date math passes.
    """
    base = load_event_spec(_MOTHERS_DAY)
    now = utcnow()
    spec = dataclasses.replace(base, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=24))
    fake = lambda now=None: spec
    monkeypatch.setattr(event_state, "active_event_spec", fake)
    from app.routers import events as _events_router
    monkeypatch.setattr(_events_router, "active_event_spec", fake)
    return spec


def _register(client) -> dict:
    email = f"evtshop+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_active_event_exposes_banner(client, active_mothers_day) -> None:
    hdr = _register(client)
    body = client.get("/events/active", headers=hdr).json()

    assert body.get("banner") is not None, "banner should be on the payload"
    banner = body["banner"]
    assert banner["hero_template_code"] == "applecrumb"
    assert banner["shard_cost"] == 8
    assert banner["per_account_cap"] == 5
    # Fresh account owns none of the featured hero yet.
    assert banner["owned"] == 0


def test_active_event_exposes_bundle_unpurchased(client, active_mothers_day) -> None:
    hdr = _register(client)
    body = client.get("/events/active", headers=hdr).json()

    assert body.get("bundle") is not None, "bundle should be on the payload"
    bundle = body["bundle"]
    assert bundle["sku"] == "mothers_day_2026_bouquet"
    assert bundle["price_cents"] == 1199
    assert bundle["purchased"] is False
