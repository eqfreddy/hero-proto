"""Post-deploy startup / health check. Run this after starting the server or
after any config change — it validates that the backend is in a usable state.

Exits 0 if everything is healthy, 1 on any failure. Prints each check result
so an operator can see at a glance what's wrong when something fails.

Usage (server must be running):
    uv run python -m scripts.startup_check
    # or against a remote deploy:
    HEROPROTO_BASE=https://your-domain uv run python -m scripts.startup_check

Environment knobs:
    HEROPROTO_BASE            — base URL (default http://127.0.0.1:8000)
    STARTUP_CHECK_ADMIN_EMAIL — email of an admin to test admin surfaces with.
                                If set, script will log in and verify /admin/*
                                endpoints. If unset, admin checks are skipped
                                with a warning (not a failure).
    STARTUP_CHECK_ADMIN_PASS  — password for the above.
    STARTUP_CHECK_EXPECT_STRIPE=1 — hard-fail if Stripe checkout endpoint returns
                                    503 instead of 409 (503 means not configured).
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

BASE = os.environ.get("HEROPROTO_BASE", "http://127.0.0.1:8000").rstrip("/")
ADMIN_EMAIL = os.environ.get("STARTUP_CHECK_ADMIN_EMAIL", "")
ADMIN_PASS = os.environ.get("STARTUP_CHECK_ADMIN_PASS", "")
EXPECT_STRIPE = os.environ.get("STARTUP_CHECK_EXPECT_STRIPE") == "1"


# ANSI colors — degrade gracefully on Windows CMD without colorama.
GREEN = "\033[32m" if sys.stdout.isatty() else ""
RED = "\033[31m" if sys.stdout.isatty() else ""
YELLOW = "\033[33m" if sys.stdout.isatty() else ""
DIM = "\033[2m" if sys.stdout.isatty() else ""
RESET = "\033[0m" if sys.stdout.isatty() else ""


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    warning: bool = False  # ok=True but with a caveat worth surfacing


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)

    def ok(self, name: str, detail: str = "") -> None:
        self.checks.append(CheckResult(name, ok=True, detail=detail))

    def warn(self, name: str, detail: str) -> None:
        self.checks.append(CheckResult(name, ok=True, detail=detail, warning=True))

    def fail(self, name: str, detail: str) -> None:
        self.checks.append(CheckResult(name, ok=False, detail=detail))

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)

    def print(self) -> None:
        for c in self.checks:
            if not c.ok:
                tag = f"{RED}FAIL{RESET}"
            elif c.warning:
                tag = f"{YELLOW}WARN{RESET}"
            else:
                tag = f"{GREEN} OK {RESET}"
            line = f"[{tag}] {c.name}"
            if c.detail:
                line += f" {DIM}-- {c.detail}{RESET}"
            print(line)


async def check_liveness(client: httpx.AsyncClient, r: Report) -> None:
    name = "/healthz responds 200"
    try:
        resp = await client.get("/healthz")
    except Exception as e:
        r.fail(name, f"network error: {e}")
        return
    if resp.status_code != 200:
        r.fail(name, f"got HTTP {resp.status_code}")
        return
    body = resp.json()
    if body.get("status") != "ok":
        r.fail(name, f"body: {body}")
        return
    r.ok(name, f"env={body.get('env')}")


async def check_worker(client: httpx.AsyncClient, r: Report) -> None:
    name = "/worker/status shows recent tick"
    try:
        resp = await client.get("/worker/status")
    except Exception as e:
        r.fail(name, f"network error: {e}")
        return
    if resp.status_code != 200:
        r.fail(name, f"got HTTP {resp.status_code}")
        return
    body = resp.json()
    if not body.get("enabled"):
        r.warn(name, "worker disabled (expected on web-only instances)")
        return
    last = body.get("last_tick_at")
    if not last:
        r.fail(name, "enabled but never ticked (worker loop didn't run once)")
        return
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        age_s = (datetime.now(timezone.utc) - last_dt).total_seconds()
    except Exception:
        r.fail(name, f"unparseable last_tick_at: {last}")
        return
    if age_s > 180:  # 3 minutes
        r.fail(name, f"last tick was {age_s:.0f}s ago (stale)")
        return
    restarts = body.get("restarts", 0)
    failed = body.get("ticks_failed", 0)
    detail = f"last tick {age_s:.0f}s ago, ticks={body.get('ticks_total')}"
    if failed:
        detail += f", failures={failed}"
    if restarts:
        detail += f", supervisor restarts={restarts}"
    (r.warn if (failed or restarts) else r.ok)(name, detail)


async def check_metrics(client: httpx.AsyncClient, r: Report) -> None:
    name = "/metrics exposes Prometheus counters"
    try:
        resp = await client.get("/metrics")
    except Exception as e:
        r.fail(name, f"network error: {e}")
        return
    if resp.status_code != 200:
        r.fail(name, f"got HTTP {resp.status_code}")
        return
    text = resp.text
    missing = [m for m in ("requests_total", "battles_total", "summons_total") if m not in text]
    if missing:
        r.fail(name, f"missing counters: {missing}")
        return
    r.ok(name, f"{len(text.splitlines())} lines of Prometheus text")


async def check_migrations_applied(client: httpx.AsyncClient, r: Report) -> None:
    """If the server started clean, /stages returns seeded data. A 500 or empty
    response suggests the migration or seed step was skipped."""
    name = "Database migrations + content seeded"
    try:
        resp = await client.get("/stages")
    except Exception as e:
        r.fail(name, f"network error: {e}")
        return
    if resp.status_code != 200:
        r.fail(name, f"/stages returned HTTP {resp.status_code}")
        return
    stages = resp.json()
    if not stages:
        r.fail(name, "/stages returned [] — run `python -c 'from app.seed import seed; seed()'`")
        return
    r.ok(name, f"{len(stages)} stages present")


async def check_auth_register_login(client: httpx.AsyncClient, r: Report) -> None:
    """Can a brand-new account register + log in?"""
    import random
    email = f"startup_check+{random.randint(100000, 999999)}@example.com"
    try:
        reg = await client.post(
            "/auth/register", json={"email": email, "password": "hunter22-check"},
        )
    except Exception as e:
        r.fail("Registration round-trip", f"network error: {e}")
        return
    if reg.status_code != 201:
        r.fail("Registration round-trip", f"register HTTP {reg.status_code}: {reg.text[:120]}")
        return
    if not reg.json().get("access_token"):
        r.fail("Registration round-trip", "no access_token in response")
        return
    if not reg.json().get("refresh_token"):
        r.warn("Registration round-trip", "no refresh_token — auth sprint E not deployed?")
        return

    # Now login with the same credentials.
    try:
        lg = await client.post(
            "/auth/login", json={"email": email, "password": "hunter22-check"},
        )
    except Exception as e:
        r.fail("Registration round-trip", f"login network error: {e}")
        return
    if lg.status_code != 200:
        r.fail("Registration round-trip", f"login HTTP {lg.status_code}")
        return
    r.ok("Registration round-trip", email)


async def check_admin_surfaces(client: httpx.AsyncClient, r: Report) -> None:
    """If STARTUP_CHECK_ADMIN_EMAIL/PASS provided, log in and verify the admin
    endpoints respond sensibly."""
    if not (ADMIN_EMAIL and ADMIN_PASS):
        r.warn(
            "Admin surface check",
            "skipped (set STARTUP_CHECK_ADMIN_EMAIL + STARTUP_CHECK_ADMIN_PASS to enable)",
        )
        return
    try:
        lg = await client.post(
            "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        )
    except Exception as e:
        r.fail("Admin login", f"network error: {e}")
        return
    if lg.status_code != 200:
        r.fail("Admin login", f"HTTP {lg.status_code}: {lg.text[:120]}")
        return
    body = lg.json()
    # 2FA path returns a challenge instead of tokens — that's fine, still proves the
    # account exists + the flow is wired.
    if body.get("status") == "totp_required":
        r.warn(
            "Admin login",
            "returned TOTP challenge — finish 2FA to validate /admin/*",
        )
        return
    token = body.get("access_token")
    if not token:
        r.fail("Admin login", "no access_token in login response")
        return

    auth = {"Authorization": f"Bearer {token}"}

    # /admin/stats — minimal admin sanity.
    resp = await client.get("/admin/stats", headers=auth)
    if resp.status_code == 403:
        r.fail(
            "Admin login",
            f"{ADMIN_EMAIL} is not an admin — promote via "
            f"`python -m app.admin promote {ADMIN_EMAIL}`",
        )
        return
    if resp.status_code != 200:
        r.fail("/admin/stats", f"HTTP {resp.status_code}")
        return
    stats = resp.json()
    r.ok(
        "Admin login + /admin/stats",
        f"accounts={stats.get('accounts_total')} battles_24h={stats.get('battles_last_24h')}",
    )

    # /admin/analytics/overview — rich dashboard.
    resp = await client.get("/admin/analytics/overview", headers=auth)
    if resp.status_code != 200:
        r.fail("/admin/analytics/overview", f"HTTP {resp.status_code}")
        return
    a = resp.json()
    r.ok(
        "Admin analytics overview",
        f"dau={a.get('accounts_dau')} wau={a.get('accounts_wau')} "
        f"payers={a.get('payers_total')} rev_total_cents={a['revenue']['total_cents']}",
    )


async def check_stripe_configured(client: httpx.AsyncClient, r: Report) -> None:
    """If EXPECT_STRIPE=1, /shop/checkout/stripe should return 401 (needs auth)
    or 409 (needs a known sku), not 503 (not configured)."""
    if not EXPECT_STRIPE:
        r.warn(
            "Stripe configured",
            "skipped (set STARTUP_CHECK_EXPECT_STRIPE=1 to require real Stripe keys)",
        )
        return
    # Unauthenticated call -> must not be 503 (not-configured).
    resp = await client.post("/shop/checkout/stripe", json={"sku": "gems_small"})
    if resp.status_code == 503:
        r.fail("Stripe configured", "503 from /shop/checkout/stripe — HEROPROTO_STRIPE_API_KEY unset")
        return
    r.ok("Stripe configured", f"responded {resp.status_code} (expected 401/422 for unauth)")


async def check_announcements_endpoint(client: httpx.AsyncClient, r: Report) -> None:
    """Smoke the public MOTD endpoint — it should always respond 200 with a list."""
    try:
        resp = await client.get("/announcements/active")
    except Exception as e:
        r.fail("Announcements endpoint", f"network error: {e}")
        return
    if resp.status_code != 200:
        r.fail("Announcements endpoint", f"HTTP {resp.status_code}")
        return
    body = resp.json()
    if not isinstance(body, list):
        r.fail("Announcements endpoint", f"expected list, got {type(body).__name__}")
        return
    r.ok("Announcements endpoint", f"{len(body)} active")


async def check_static_pages(client: httpx.AsyncClient, r: Report) -> None:
    """The dashboard + battle viewers should serve 200."""
    pages = ("/app/", "/app/battle-setup.html", "/app/battle-replay.html",
             "/app/battle-phaser.html", "/app/roster.html")
    for p in pages:
        try:
            resp = await client.get(p)
        except Exception as e:
            r.fail(f"Static page {p}", f"network error: {e}")
            continue
        if resp.status_code != 200:
            r.fail(f"Static page {p}", f"HTTP {resp.status_code}")
            continue
    # Only announce success if every one passed.
    if all(c.ok for c in r.checks if c.name.startswith("Static page ")):
        r.ok("Static pages", f"{len(pages)} pages all 200")


async def main() -> int:
    print(f"startup_check -> {BASE}")
    print()
    r = Report()
    async with httpx.AsyncClient(base_url=BASE, timeout=15.0) as client:
        await check_liveness(client, r)
        await check_worker(client, r)
        await check_metrics(client, r)
        await check_migrations_applied(client, r)
        await check_auth_register_login(client, r)
        await check_announcements_endpoint(client, r)
        await check_static_pages(client, r)
        await check_admin_surfaces(client, r)
        await check_stripe_configured(client, r)

    r.print()
    print()
    total = len(r.checks)
    failed = sum(1 for c in r.checks if not c.ok)
    warned = sum(1 for c in r.checks if c.ok and c.warning)
    passed = total - failed - warned
    if failed:
        print(f"{RED}STARTUP CHECK FAILED{RESET} — {failed} fail, {warned} warn, {passed} ok")
        return 1
    if warned:
        print(f"{YELLOW}STARTUP CHECK OK WITH WARNINGS{RESET} — {warned} warn, {passed} ok")
        return 0
    print(f"{GREEN}STARTUP CHECK PASSED{RESET} — {passed} checks ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
