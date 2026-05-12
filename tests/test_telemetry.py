"""POST /telemetry/event — auth + forwards to analytics.track."""

from __future__ import annotations

import random
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _record_events():
    recorded: list[dict] = []

    def _recorder(event, account_id, properties=None):
        recorded.append({"event": event, "account_id": account_id, "properties": properties or {}})

    with patch("app.analytics.track", side_effect=_recorder):
        yield recorded


def _register(client, prefix: str = "tele") -> tuple[dict, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me_id = client.get("/me", headers=hdr).json()["id"]
    return hdr, me_id


def test_telemetry_rejects_unauth(client) -> None:
    r = client.post("/telemetry/event", json={"name": "battle3d.first_frame_ms", "value": 26.8})
    assert r.status_code == 401


def test_telemetry_forwards_to_analytics(client) -> None:
    hdr, account_id = _register(client)
    with _record_events() as events:
        r = client.post(
            "/telemetry/event",
            json={"name": "battle3d.first_frame_ms", "value": 26.8},
            headers=hdr,
        )
    assert r.status_code == 204, r.text
    assert any(e["event"] == "battle3d.first_frame_ms" for e in events)
    captured = next(e for e in events if e["event"] == "battle3d.first_frame_ms")
    assert captured["account_id"] == account_id
    assert captured["properties"].get("value") == 26.8


def test_telemetry_passes_meta_bag(client) -> None:
    hdr, _ = _register(client, prefix="tele-meta")
    with _record_events() as events:
        r = client.post(
            "/telemetry/event",
            json={
                "name": "battle3d.diorama_loaded",
                "meta": {"theme": "cubicle-farm", "size_mb": 0.6},
            },
            headers=hdr,
        )
    assert r.status_code == 204, r.text
    captured = next(e for e in events if e["event"] == "battle3d.diorama_loaded")
    assert captured["properties"].get("theme") == "cubicle-farm"
    assert captured["properties"].get("size_mb") == 0.6


def test_telemetry_caps_meta_to_12_keys(client) -> None:
    hdr, _ = _register(client, prefix="tele-cap")
    big_meta = {f"k{i}": i for i in range(30)}
    with _record_events() as events:
        r = client.post(
            "/telemetry/event",
            json={"name": "battle3d.spam_test", "meta": big_meta},
            headers=hdr,
        )
    assert r.status_code == 204, r.text
    captured = next(e for e in events if e["event"] == "battle3d.spam_test")
    # value not present + at most 12 keys forwarded.
    assert "value" not in captured["properties"]
    assert len(captured["properties"]) <= 12


def test_telemetry_rejects_blank_or_oversized_name(client) -> None:
    hdr, _ = _register(client, prefix="tele-rej")
    r = client.post("/telemetry/event", json={"name": ""}, headers=hdr)
    assert r.status_code == 422
    r = client.post("/telemetry/event", json={"name": "x" * 200}, headers=hdr)
    assert r.status_code == 422
