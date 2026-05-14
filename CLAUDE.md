# CLAUDE.md — hero-proto

Project-scoped guidance for Claude Code. Loads in addition to the global `~/.claude/CLAUDE.md` working-style block whenever CWD is inside this repo.

## What this is

Gacha + turn-based team combat RPG backend. IT-themed heroes (ticket gremlins, oncall warriors, shadow-IT operators) fight through outage/audit/migration stages. Working alpha — full F2P surface live (accounts, gacha, arena, guilds, raids, store with Stripe, admin tools, observability). No final art yet.

**Status one-liner:** 806 backend tests + 84 frontend vitest tests passing. Phase 4 (mobile/wrap/store/push) ✅. Shard remap shipped 2026-05-12. Quaternius rig migration shipped same day.

## Stack

- **Python 3.13**, **`uv`** for env + run (not pip / poetry / venv directly)
- **FastAPI** + **SQLAlchemy 2** + **Alembic** migrations
- **SQLite** locally, **Postgres** in CI on every push (matrix tested)
- **Redis** for rate limiter (horizontal-scale ready)
- **React SPA** (Vite) at `/app`, built into `app/static/spa/`
- **Capacitor** mobile wrap in `mobile/`
- **Anthropic Claude API** wired for content generation (uses `anthropic>=0.50.0`)
- **Stripe + Apple StoreKit + Google Play Billing** adapters live
- **Prometheus** `/metrics`, **Sentry** (DSN-gated), JSON logs with request IDs

## Commands

```bash
# Install + DB up
uv sync --all-extras
uv run alembic upgrade head
uv run python -c "from app.seed import seed; seed()"

# Run server
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
# → http://127.0.0.1:8000/app/   (SPA dashboard)
# → http://127.0.0.1:8000/docs    (OpenAPI)

# Tests
uv run pytest                              # backend (806 tests)
uv run pytest tests/test_phase2_acceptance.py  # bright-line e2e

# Frontend
cd frontend && bun test                     # vitest, 84 tests

# Acceptance scripts (live server required)
uv run python scripts/startup_check.py     # admin/operator health
uv run python scripts/client_walkthrough.py # 17-section feature tour

# Postgres smoke (Docker Desktop required)
bash scripts/postgres_stack_validate.sh
```

## Project layout

- `app/` — FastAPI app, routers, models, services (the meat)
- `alembic/` — migrations; latest = `f9fcd159c6dd` (shard remap)
- `frontend/` — Vite + React SPA, built to `app/static/spa/`
- `mobile/` — Capacitor scaffold (`capacitor.config.ts` → `app/static/spa`)
- `app/static/spa/` — built SPA output (committed; vanilla-JS shell at `app/partials/*` is legacy)
- `app/static/heroes/` — 33 portrait + 33 bust PNGs (CraftPix-licensed)
- `scripts/` — acceptance + ops scripts (startup_check, client_walkthrough, postgres_stack_validate, backup_db)
- `tests/` — unit + acceptance (`test_phase1_acceptance.py`, `test_phase2_acceptance.py`)
- `docs/` — RUNBOOK, PRD, PHASE_2_HUMAN_TEST, PLAN_B_INTEGRATION, BATTLE_RIG_EVENT_MAPPING, BATTLE_VISUALS_STACK
- `TODO.md` — living roadmap + status log. **Read this first** to know what's recently shipped.

## Conventions

- **uv is non-negotiable.** Always `uv run`, never `python` directly.
- **Drop `uv.lock` from commits.** It has CRLF churn on Windows that produces noisy no-op diffs. Pattern in commit-push skill already handles this.
- **Alembic migrations auto-run on Fly via `app/main.py`.** Don't commit data-only migrations; if a migration touches data, gate it idempotently.
- **Tests are the contract.** 806/2-skipped on backend is the green line. Don't merge red. The phase acceptance tests (`test_phase{1,2}_acceptance.py`) are bright-line e2e.
- **Shards, not fodder.** Duplicate hero ascension uses **template shards** (5/15/40/100 per tier 1→5) via `app/template_shards.py::spend()`. Fodder-based `/heroes/{id}/ascend` was deleted 2026-05-12 — don't reintroduce it. Use `/ascend-with-shards`.
- **Faction synergy is baked into base stats before sim.** Don't recompute on the fly.
- **Combat log cap = 200 entries.** `trim_combat_log()` handles this.
- **Per-turn timer is server-authoritative** (120s default). Client renders countdown; server forfeits on poll if expired.

## What's mid-flight

- **Quaternius rig migration** complete for 6 archetypes (knight/barbarian/mage/ranger/rogue/rogue_hooded). Engineer/Monk staged at `frontend/public/battle-3d/heroes/monk.glb`.
- **CraftPix sprite system** — 26 rigs, each `template_code` mapped to one.
- **Per-turn countdown timer** live for interactive combat + raids.
- **Battle 3D layout polish** in progress — see TODO.md "Follow-ups from 2026-05-10 Battle 3D Viewer v1".
- **Music/BGM mapping**: 6 alignment-themed tracks staged in `sound/` (3 dark / 3 light). See Content section of TODO.md.
- **Exile + other races brainstorm** — open, content section of TODO.md.

## What NOT to do

- Don't suggest removing the Postgres CI matrix. SQLite works locally but Fly runs Postgres.
- Don't add new monetization without checking against the existing F2P surface — see TODO.md "Engagement / monetization design".
- Don't restyle the vanilla-JS shell at `app/partials/*` — it's legacy, SPA is primary.
- Don't introduce a third character generation. Original Gary + Gary 2.0 (in `cluster-of-fuckery`) is enough; this project uses Quaternius/CraftPix rigs separately.
- Don't ship without running `client_walkthrough.py` if the change touches a user-visible surface.

## External references

- **Linear / GitHub issues** — not used here; TODO.md is the source of truth
- **PostHog** — optional analytics runtime (degrades to no-op if not installed)
- **Fly.io** app: `hero-proto`
