"""Worker supervisor: respawn on crash, health telemetry, /worker/status endpoint."""

from __future__ import annotations

import asyncio
import pytest

from app import worker as worker_module
from app.worker import (
    WorkerHealth,
    _tick_once,
    health as global_health,
    supervised_worker_loop,
)


@pytest.fixture(autouse=True)
def _reset_health():
    """Reset the process-wide health singleton between tests."""
    yield
    global_health.last_tick_at = None
    global_health.last_tick_success = True
    global_health.last_error = ""
    global_health.ticks_total = 0
    global_health.ticks_failed = 0
    global_health.restarts = 0


@pytest.mark.asyncio
async def test_tick_once_updates_health_on_success(monkeypatch) -> None:
    """Successful job run should bump ticks_total + stamp last_tick_at + clear last_error."""
    ran = []

    def fake_jobs():
        ran.append(True)

    monkeypatch.setattr(worker_module, "_run_jobs", fake_jobs)

    await _tick_once()

    assert ran == [True]
    assert global_health.ticks_total == 1
    assert global_health.ticks_failed == 0
    assert global_health.last_tick_success is True
    assert global_health.last_tick_at is not None
    assert global_health.last_error == ""


@pytest.mark.asyncio
async def test_tick_once_swallows_job_exception(monkeypatch) -> None:
    """A crashing job must not propagate — the loop keeps marching."""

    def broken_jobs():
        raise RuntimeError("db exploded")

    monkeypatch.setattr(worker_module, "_run_jobs", broken_jobs)

    # Must not raise.
    await _tick_once()

    assert global_health.ticks_total == 1
    assert global_health.ticks_failed == 1
    assert global_health.last_tick_success is False
    assert "db exploded" in global_health.last_error


@pytest.mark.asyncio
async def test_supervisor_respawns_after_loop_crash(monkeypatch) -> None:
    """If worker_loop raises a non-Cancelled exception, the supervisor logs it,
    bumps the restart counter, backs off, and starts a fresh loop."""
    # Stand in a fake worker_loop that crashes on the first run, completes on the second.
    calls = {"count": 0}

    async def fake_loop() -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        # Second run: return immediately so supervised loop can terminate via cancellation.
        await asyncio.sleep(0)

    monkeypatch.setattr(worker_module, "worker_loop", fake_loop)
    # Short backoff so the test is fast.
    monkeypatch.setattr(worker_module, "SUPERVISOR_RESTART_DELAY_SECONDS", 0.01)
    monkeypatch.setattr(worker_module, "SUPERVISOR_RESTART_DELAY_MAX", 0.02)

    task = asyncio.create_task(supervised_worker_loop())
    # Give it enough ticks for one crash + restart + second invocation + respawn loop.
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls["count"] >= 2, "supervisor should respawn after the first crash"
    assert global_health.restarts >= 1


@pytest.mark.asyncio
async def test_supervisor_propagates_cancellation(monkeypatch) -> None:
    """Clean shutdown (CancelledError) must escape the supervisor, not be swallowed."""
    started = asyncio.Event()

    async def fake_loop() -> None:
        started.set()
        # Block until the task is cancelled.
        await asyncio.sleep(10)

    monkeypatch.setattr(worker_module, "worker_loop", fake_loop)

    task = asyncio.create_task(supervised_worker_loop())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # No spurious restarts from a clean shutdown.
    assert global_health.restarts == 0


def test_worker_status_endpoint_shape(client) -> None:
    """/worker/status returns the expected fields even pre-first-tick."""
    r = client.get("/worker/status")
    assert r.status_code == 200
    body = r.json()
    for key in ("enabled", "last_tick_at", "last_tick_success", "last_error",
                "ticks_total", "ticks_failed", "restarts"):
        assert key in body, f"missing field: {key}"


def test_healthz_omits_worker_when_disabled(client, monkeypatch) -> None:
    """With worker_enabled=False, /healthz doesn't include a worker block."""
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "worker_enabled", False)
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    # Env is 'test' in this fixture anyway, so worker block shouldn't be present.
    assert "worker" not in body
