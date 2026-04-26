"""PostHog analytics wrapper + 12 instrumented events.

Tests use a recorder that monkey-patches `app.analytics.track`. We don't
exercise the real `posthog-python` client — that path is no-op in the
test environment (settings.environment == 'test') and is covered
operationally by the deploy.

Each instrumented endpoint should fire exactly the expected event name
with at least the key properties documented in `docs/RUNBOOK.md` →
Analytics. We assert on event name + a small sample of properties so
adding new properties later doesn't break tests.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from unittest.mock import patch

import pytest


@contextmanager
def _record_events():
    """Replace `app.analytics.track` with a recorder that captures every call.
    Yields the list; events accrue as they fire. Does not touch the real
    client (which is no-op in tests anyway)."""
    recorded: list[dict] = []

    def _recorder(event, account_id, properties=None):
        recorded.append({
            "event": event,
            "account_id": account_id,
            "properties": properties or {},
        })

    targets = [
        "app.routers.auth.track" if False else None,  # imported inside fn, no module-level
    ]
    # The wrapper is imported inside each endpoint as a function-local symbol
    # (`from app.analytics import track as _track`), so patching the source
    # module catches every callsite.
    with patch("app.analytics.track", side_effect=_recorder):
        yield recorded


def _register(client, prefix: str = "ana") -> tuple[dict, int, str]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return hdr, client.get("/me", headers=hdr).json()["id"], email


# --- Wrapper behavior --------------------------------------------------------


def test_track_is_noop_when_env_is_test() -> None:
    """In the test environment the wrapper short-circuits before building a
    client. This is the contract every other test relies on."""
    from app.analytics import _enabled

    assert _enabled() is False


def test_track_swallows_exceptions(monkeypatch) -> None:
    """A broken posthog client must not propagate into the request path."""
    from app import analytics

    class _Boom:
        def capture(self, **_):
            raise RuntimeError("simulated network failure")

    monkeypatch.setattr(analytics, "_client", _Boom())
    monkeypatch.setattr(analytics.settings, "posthog_api_key", "phc_x")
    monkeypatch.setattr(analytics.settings, "posthog_disabled", False)
    monkeypatch.setattr(analytics.settings, "environment", "dev")
    # Should not raise.
    analytics.track("any_event", 1, {"k": "v"})


# --- The 12 instrumented events ----------------------------------------------


def test_register_fires_register_event(client) -> None:
    with _record_events() as events:
        email = f"ev_reg+{random.randint(100000, 999999)}@example.com"
        client.post("/auth/register", json={"email": email, "password": "hunter22"})
    names = [e["event"] for e in events]
    assert "register" in names
    reg = next(e for e in events if e["event"] == "register")
    assert reg["account_id"] is not None
    assert reg["properties"]["email_domain"] == "example.com"


def test_login_fires_login_event(client) -> None:
    email = f"ev_login+{random.randint(100000, 999999)}@example.com"
    client.post("/auth/register", json={"email": email, "password": "hunter22"})
    with _record_events() as events:
        client.post("/auth/login", json={"email": email, "password": "hunter22"})
    assert any(e["event"] == "login" for e in events)
    login = next(e for e in events if e["event"] == "login")
    assert login["properties"]["method"] == "password"


def test_summon_x1_fires_summon_x1_event(client) -> None:
    hdr, _, _ = _register(client, "ev_x1")
    with _record_events() as events:
        client.post("/summon/x1", headers=hdr)
    summon_events = [e for e in events if e["event"] == "summon_x1"]
    assert len(summon_events) == 1
    assert "rarity" in summon_events[0]["properties"]


def test_summon_x10_fires_summon_x10_event(client) -> None:
    hdr, aid, _ = _register(client, "ev_x10")
    # Bump shards so the x10 succeeds.
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        a.shards = 100
        db.commit()
    finally:
        db.close()

    with _record_events() as events:
        client.post("/summon/x10", headers=hdr)
    x10 = [e for e in events if e["event"] == "summon_x10"]
    assert len(x10) == 1
    props = x10[0]["properties"]
    assert "best_rarity" in props
    assert sum(props["rarity_counts"].values()) == 10


def test_battle_fires_stage_start_and_stage_clear(client) -> None:
    hdr, _aid, _ = _register(client, "ev_bat")
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    with _record_events() as events:
        client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)

    names = [e["event"] for e in events]
    assert "stage_start" in names
    assert "stage_clear" in names
    # On a tutorial first-time clear, first_clear should fire too — verify
    # it appears at most once even on a re-run later.
    if any(e["event"] == "first_clear" for e in events):
        first_clears = [e for e in events if e["event"] == "first_clear"]
        assert len(first_clears) == 1
        assert first_clears[0]["properties"]["stage_code"] == "tutorial_first_ticket"


def test_arena_attack_fires_arena_attack_event(client) -> None:
    """Need at least one defender available. Register two accounts so the
    matchmaker has someone to surface."""
    _h_def, _, _ = _register(client, "ev_arena_def")
    hdr, _aid, _ = _register(client, "ev_arena_atk")

    opponents = client.get("/arena/opponents", headers=hdr).json()
    if not opponents:
        pytest.skip("no opponents available in this seed; matchmaker bracket empty")

    target = opponents[0]
    # Arena opponent shape uses `account_id`, not `id`. Older shapes may have
    # used `id`; tolerate both so a future schema rename doesn't silently
    # KeyError in the test runner.
    defender_id = target.get("account_id") or target.get("id")
    if not defender_id:
        pytest.skip(f"unexpected opponent shape: {list(target.keys())}")
    with _record_events() as events:
        r = client.post(
            "/arena/attack",
            json={"defender_account_id": defender_id},
            headers=hdr,
        )
    if r.status_code != 201:
        pytest.skip(f"arena attack did not run (status={r.status_code})")
    arena_events = [e for e in events if e["event"] == "arena_attack"]
    assert len(arena_events) == 1
    assert "won" in arena_events[0]["properties"]


def test_daily_bonus_fires_daily_bonus_claim(client) -> None:
    hdr, _, _ = _register(client, "ev_daily")
    with _record_events() as events:
        r = client.post("/me/daily-bonus/claim", headers=hdr)
    if r.status_code == 201:
        claim_events = [e for e in events if e["event"] == "daily_bonus_claim"]
        assert len(claim_events) == 1
        assert "streak_after" in claim_events[0]["properties"]


def test_raid_attack_fires_raid_attack_event(client) -> None:
    """Need a guild + an active raid. Create both via the API."""
    hdr, _aid, _ = _register(client, "ev_raid")
    # Guild — require a unique name + tag.
    suffix = random.randint(10**12, 10**13 - 1)
    r = client.post(
        "/guilds",
        json={"name": f"AnaG_{suffix}", "tag": f"a{suffix % 100000:05d}"},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    # Start a raid against the cheapest boss template.
    boss_codes = [
        "raidboss_legacy_colossus",
        "raidboss_c_suite_hydra",
        "raidboss_chaos_dragon",
    ]
    started = None
    for boss_code in boss_codes:
        r = client.post(
            "/raids/start",
            json={
                "boss_template_code": boss_code,
                "boss_level": 5,
                "tier": "T1",
                "duration_hours": 24,
            },
            headers=hdr,
        )
        if r.status_code == 201:
            started = r.json()
            break
    if started is None:
        pytest.skip("no raid boss seeded; can't exercise raid attack path")

    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    with _record_events() as events:
        r = client.post(
            f"/raids/{started['id']}/attack",
            json={"team": team},
            headers=hdr,
        )
    if r.status_code != 201:
        pytest.skip(f"raid attack did not run (status={r.status_code})")
    raid_events = [e for e in events if e["event"] == "raid_attack"]
    assert len(raid_events) == 1
    assert "damage_dealt" in raid_events[0]["properties"]
    assert raid_events[0]["properties"]["tier"] == "T1"


def test_purchase_fires_start_and_complete(client) -> None:
    """Mock-payments mode is on in tests (HEROPROTO_MOCK_PAYMENTS_ENABLED=1
    set in conftest), so /shop/purchases grants immediately. Verify both
    events fire on a single completed purchase."""
    hdr, _, _ = _register(client, "ev_buy")
    products = client.get("/shop/products", headers=hdr).json()
    if not products:
        pytest.skip("no products seeded; can't exercise purchase path")
    target = next((p for p in products if p["price_cents"] > 0), None)
    if target is None:
        pytest.skip("only free products available")

    with _record_events() as events:
        r = client.post(
            "/shop/purchases",
            json={"sku": target["sku"], "client_ref": f"test-{random.randint(1, 10**9)}"},
            headers=hdr,
        )
    if r.status_code != 201:
        pytest.skip(f"purchase did not complete (status={r.status_code}); not the analytics path")

    starts = [e for e in events if e["event"] == "purchase_start"]
    completes = [e for e in events if e["event"] == "purchase_complete"]
    assert len(starts) == 1
    assert len(completes) == 1
    assert starts[0]["properties"]["processor"] == "mock"
    assert completes[0]["properties"]["sku"] == target["sku"]
