"""Sanity tests for scripts/activate_event.py — every events/*.json parses,
the activation pipeline writes the expected rows, deactivation tears them
down. Catches accidental breakage of the event spec format.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AdminAnnouncement, LiveOpsEvent, ShopProduct
from scripts.activate_event import _activate, _deactivate, _load_spec, _parse_iso

EVENTS_DIR = Path(__file__).resolve().parents[1] / "events"


def test_every_event_spec_parses() -> None:
    """Every JSON file in events/ must satisfy the spec contract."""
    found = list(EVENTS_DIR.glob("*.json"))
    assert found, "no event specs found — events/ should ship with at least one"
    for path in found:
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert "id" in spec, f"{path.name} missing id"
        assert "starts_at" in spec and "ends_at" in spec, f"{path.name} missing timestamps"
        starts = _parse_iso(spec["starts_at"])
        ends = _parse_iso(spec["ends_at"])
        assert ends > starts, f"{path.name}: ends_at must be after starts_at"
        assert isinstance(spec.get("liveops", []), list)
        assert isinstance(spec.get("shop", []), list)


def test_activate_then_deactivate_round_trip(client) -> None:
    """Activate Canada Day → see the rows. Deactivate → rows suppressed."""
    spec_path = EVENTS_DIR / "2026-07-01_canada_day.json"
    spec = _load_spec(spec_path)

    rc = _activate(spec)
    assert rc == 0

    with SessionLocal() as db:
        ann = db.scalar(
            select(AdminAnnouncement).where(AdminAnnouncement.body.like(f"%[event:{spec['id']}]%"))
        )
        assert ann is not None
        assert ann.is_active is True
        liv = db.scalar(select(LiveOpsEvent).where(LiveOpsEvent.name == "Canada Day 2x"))
        assert liv is not None
        sku = db.scalar(select(ShopProduct).where(ShopProduct.sku == "canada_day_2026_pack"))
        assert sku is not None
        assert sku.per_account_limit == 1

    rc = _deactivate(spec)
    assert rc == 0

    with SessionLocal() as db:
        ann = db.scalar(
            select(AdminAnnouncement).where(AdminAnnouncement.body.like(f"%[event:{spec['id']}]%"))
        )
        assert ann.is_active is False
        sku = db.scalar(select(ShopProduct).where(ShopProduct.sku == "canada_day_2026_pack"))
        assert sku.sort_order == 9999  # sentinel — sunk to bottom
        assert sku.per_account_limit == 1


def test_activate_rejects_bad_iso_timestamps() -> None:
    """Bad timestamps fail at parse, not silently."""
    bogus = {
        "id": "bogus",
        "starts_at": "not-a-date",
        "ends_at": "2026-07-04T00:00:00Z",
    }
    import pytest
    with pytest.raises(ValueError):
        _parse_iso(bogus["starts_at"])


def test_activate_rejects_inverted_timestamps(tmp_path: Path) -> None:
    """starts_at after ends_at → exit code 1."""
    spec = {
        "id": "inverted",
        "starts_at": "2026-07-05T00:00:00Z",
        "ends_at": "2026-07-04T00:00:00Z",
    }
    rc = _activate(spec)
    assert rc == 1


def test_activate_is_idempotent(client) -> None:
    """Re-running activation updates in place — no duplicate rows."""
    spec = _load_spec(EVENTS_DIR / "2026-07-04_summer_slowdown.json")
    _activate(spec)
    _activate(spec)  # second pass

    with SessionLocal() as db:
        # Exactly one announcement carrying this event marker.
        anns = list(db.scalars(
            select(AdminAnnouncement).where(AdminAnnouncement.body.like(f"%[event:{spec['id']}]%"))
        ))
        assert len(anns) == 1, f"expected single announcement, got {len(anns)}"
        # Exactly one shop SKU.
        skus = list(db.scalars(
            select(ShopProduct).where(ShopProduct.sku == "summer_slowdown_2026_pack")
        ))
        assert len(skus) == 1
    _deactivate(spec)
