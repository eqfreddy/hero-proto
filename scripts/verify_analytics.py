"""Smoke-test PostHog analytics — fires one of each instrumented event
against the *configured* PostHog backend so you can confirm the wiring
end-to-end before pointing real traffic at it.

Reads `HEROPROTO_POSTHOG_API_KEY` + `HEROPROTO_POSTHOG_HOST` (or
PostHog Cloud's `https://app.posthog.com` default) from the environment.
Sends 12 sentinel events from a synthetic distinct_id, flushes the
batch, and prints what to look for in the PostHog UI.

This bypasses the full app — no DB, no auth, no rate limits. It calls
`app.analytics.track()` directly with hand-crafted payloads. The point
is to verify:
  1. The key is valid and the host is reachable.
  2. Events arrive with the right names + properties.
  3. The four Phase 2 funnels (`register` → `purchase_complete`,
     `register` → `stage_clear`, `register` → `stage_start`, daily
     engagement) can resolve once real traffic lands.

Usage:
    HEROPROTO_POSTHOG_API_KEY=phc_... uv run python -m scripts.verify_analytics
    HEROPROTO_POSTHOG_API_KEY=phc_... HEROPROTO_POSTHOG_HOST=https://posthog.example.com \\
        uv run python -m scripts.verify_analytics --distinct-id "smoketest-1"

Exit codes:
    0  events captured + flushed successfully
    1  PostHog client could not be built (key missing, dep missing, etc.)
    2  unhandled exception during emission
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone


SENTINEL_EVENTS = [
    # (event_name, properties)
    ("register", {"email_domain": "example.com"}),
    ("login", {"method": "password"}),
    ("summon_x1", {"rarity": "RARE", "epic_pity_triggered": False}),
    ("summon_x10", {
        "best_rarity": "EPIC",
        "rarity_counts": {
            "COMMON": 4, "UNCOMMON": 3, "RARE": 2, "EPIC": 1,
            "LEGENDARY": 0, "MYTH": 0,
        },
        "epic_pity_triggered": False,
    }),
    ("stage_start", {
        "stage_id": 1, "stage_code": "tutorial_first_ticket",
        "stage_order": 0, "team_size": 3,
    }),
    ("stage_clear", {
        "stage_id": 1, "stage_code": "tutorial_first_ticket",
        "outcome": "WIN", "won": True, "ticks": 42,
    }),
    ("first_clear", {
        "stage_id": 1, "stage_code": "tutorial_first_ticket",
        "stage_order": 0,
    }),
    ("arena_attack", {
        "outcome": "WIN", "won": True,
        "rating_delta": 25, "rating_after": 1025,
    }),
    ("raid_attack", {
        "raid_id": 1, "tier": "T1",
        "damage_dealt": 12345, "boss_defeated": False,
        "boss_remaining_pct": 73.5,
    }),
    ("purchase_start", {
        "sku": "starter_jumpahead", "processor": "mock", "price_cents": 499,
    }),
    ("purchase_complete", {
        "sku": "starter_jumpahead", "processor": "mock",
        "price_cents": 499, "currency": "USD",
    }),
    ("daily_bonus_claim", {"streak_after": 1, "was_reset": False}),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--distinct-id",
        default=f"verify-{uuid.uuid4().hex[:12]}",
        help="distinct_id to attach to the sentinel events (default: random)",
    )
    parser.add_argument(
        "--no-flush-wait",
        action="store_true",
        help="skip the 5s sleep before shutdown (use only if you're sure)",
    )
    args = parser.parse_args()

    # Force-enable analytics regardless of HEROPROTO_ENVIRONMENT — the wrapper
    # hard-disables in 'test' env, but ops also runs this from dev sometimes.
    os.environ.setdefault("HEROPROTO_ENVIRONMENT", "dev")
    os.environ["HEROPROTO_POSTHOG_DISABLED"] = "0"

    # Import after env is set so settings pick up the override.
    from app.analytics import _enabled, _get_client, shutdown, track
    from app.config import settings

    api_key = settings.posthog_api_key
    host = settings.posthog_host
    if not api_key:
        print("HEROPROTO_POSTHOG_API_KEY is not set — nothing to verify.", file=sys.stderr)
        return 1
    if not _enabled():
        print(
            "Analytics is disabled despite the key being set. Check "
            "HEROPROTO_POSTHOG_DISABLED and HEROPROTO_ENVIRONMENT.",
            file=sys.stderr,
        )
        return 1

    client = _get_client()
    if client is None:
        print(
            "Could not build PostHog client. Is posthog-python installed? "
            "Run `uv sync --extra analytics-runtime`.",
            file=sys.stderr,
        )
        return 1

    distinct_id = args.distinct_id
    print(f"Emitting {len(SENTINEL_EVENTS)} sentinel events…")
    print(f"  host:        {host}")
    print(f"  distinct_id: {distinct_id}")
    print(f"  timestamp:   {datetime.now(timezone.utc).isoformat()}")
    print()

    failed: list[str] = []
    for event, properties in SENTINEL_EVENTS:
        properties = {**properties, "verify_run": distinct_id}
        try:
            # Bypass the wrapper's distinct-id-from-account-id logic and call
            # the client directly — we want a synthetic distinct_id that won't
            # collide with real account IDs (which are integers).
            client.capture(
                distinct_id=distinct_id,
                event=event,
                properties={
                    "env": settings.environment,
                    "request_id": f"verify-{uuid.uuid4().hex[:8]}",
                    **properties,
                },
            )
            print(f"  ✓ {event}")
        except Exception as exc:
            print(f"  ✗ {event}: {exc}", file=sys.stderr)
            failed.append(event)

    if failed:
        print(f"\nFailed to emit {len(failed)} events: {failed}", file=sys.stderr)
        return 2

    print("\nFlushing batch…")
    if not args.no_flush_wait:
        # Give the background thread time to send. PostHog's default flush
        # interval is 1s; 5s is conservative.
        import time
        time.sleep(5)
    shutdown()

    print()
    print("=" * 60)
    print("Verify in PostHog UI:")
    print("=" * 60)
    print(f"  1. Open: {host}")
    print(f"  2. Activity → Live events")
    print(f"  3. Filter by 'distinct_id = \"{distinct_id}\"'")
    print(f"  4. You should see all 12 events:")
    for event, _ in SENTINEL_EVENTS:
        print(f"       • {event}")
    print()
    print(f"  Or query Insights → SQL:")
    print(f"     SELECT event, properties FROM events")
    print(f"     WHERE distinct_id = '{distinct_id}'")
    print(f"     ORDER BY timestamp DESC")
    print()
    print("If events don't appear within ~30s:")
    print("  - check the API key (Settings → Project → Project API key)")
    print("  - check the host URL (PostHog Cloud uses https://app.posthog.com,")
    print("    self-hosted uses your domain)")
    print("  - check posthog-python is installed: `uv pip show posthog`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
