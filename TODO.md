# hero-proto — TODO & Test Reference

Living list. Tick items `[x]` as done. Add new ones at the bottom of the relevant section.

Last updated: 2026-04-23.

---

## 📊 Where we're at

- **Backend:** 22 slices shipped (1–21 + 62) + admin polish sprint.
- **Tests:** `pytest` 52/52 green. 10 E2E smoke scripts all pass against a live uvicorn.
- **Git:** `master` pushed to `github.com/eqfreddy/hero-proto` — latest commit `4d0bc36`.
- **DB:** SQLite dev, Postgres wire-up exists in `docker-compose.yml` (profile) but **not yet verified end-to-end**.
- **Frontend:** bare-bones vanilla-JS shell at `/app` — functional for smoke tests, not styled for users.

### Known papercuts surfaced recently

- **Rate limits in `.env` (10 auth/min, 120 general/min) are too tight for the full smoke suite.** Need to either raise the shipped defaults or add a `HEROPROTO_RATE_LIMIT_DISABLED=1` short-circuit for local dev.
- **Banned user's JWT is still technically valid until expiry** — blocked only by the 403 in `deps.py`. Token-version or revocation list would fix this properly.
- **`smoke_cli.py` must be invoked as `python -m scripts.smoke_cli`** (not `python scripts/smoke_cli.py`) because of the `from scripts import play_hero` line. Worth either a README note or restructuring.
- **`smoke_sets.py` doesn't gracefully handle an error payload from `/gear/mine`** — it iterates dict keys as strings and crashes with `'str' object has no attribute 'get'` instead of a clean fail. Exposed when rate-limited.

---

## 🎯 Next up — ranked candidate sprints

Each sprint is sized to be shippable in one session. Pick one; don't interleave.

### A. Hardening + footguns (small, immediate value)
Addresses the papercuts above head-on.
- [ ] **JWT version on Account** (`token_version: int`, increment on ban). `issue_token` embeds it; `decode_token` dep checks it. Banning a user now kills their session for real.
- [ ] **Sane default rate limits + dev bypass** — raise `AUTH_RATE_PER_MINUTE` / `GENERAL_RATE_PER_MINUTE` defaults, or add `HEROPROTO_RATE_LIMIT_DISABLED=1`. Ship `.env.example` aligned with the bypass.
- [ ] **Combat log pruning** — cap `Battle.log_json` entries server-side (e.g. 200 events) so long arena matches don't balloon the DB row.
- [ ] **Fix `smoke_sets.py`** to break cleanly on an error payload + fix `smoke_cli.py` invocation (either `-m` the file directly, or drop the `from scripts import` pattern).
- [ ] Tests for all of the above.

### B. Guild completeness
Entirely in `routers/guilds.py` + tests.
- [ ] `POST /guilds/{id}/promote/{account_id}` — leader promotes MEMBER → OFFICER
- [ ] `POST /guilds/{id}/transfer/{account_id}` — leader hands off without leaving
- [ ] Application / invite flow (replace "anyone can join public guilds")
- [ ] Chat pagination (currently hard-capped at 50 newest)
- [ ] `smoke_guild.py` E2E mirror

### C. Postgres validation
We claim it's supported; nothing's ever run against a real Postgres.
- [ ] Run full `pytest` against `postgresql+psycopg://…` URL
- [ ] Fix any SQLite-isms that surface (string-as-enum comparisons, `JSON` columns, etc.)
- [ ] Run the 10 E2E smokes against the compose stack
- [ ] Document the flow in `README.md`

### D. Content expansion
User-facing variety. Touches `seed.py` + content tables.
- [ ] 10–20 more hero templates (currently 25)
- [ ] 5–10 more stages (currently 10)
- [ ] "Hard mode" campaign tier (same stages, scaled stats, better rewards)
- [ ] Boss-only hero templates for raids (higher stats)
- [ ] Tutorial stage 0 / first-time walkthrough

### E. Auth hardening
Heavier — needs email-send infra decision (SES? Postmark? console sink for dev?).
- [ ] Email verification flow (send token, `GET /auth/verify?token=…`)
- [ ] Forgot-password / reset-password flow
- [ ] Refresh tokens + rotation
- [ ] 2FA (TOTP)

**Recommendation:** ship **A** next — the JWT-on-ban gap is the most embarrassing one to leave open after an admin sprint, and the rate-limit papercut bit us during this very sprint's smoke run.

---

## 🚧 Backlog — everything else

### Admin tooling (follow-ups)
- [ ] Ban should invalidate existing JWTs (see Sprint A above)
- [ ] Admin "broadcast announcement" — pinned MOTD visible on `GET /me`

### Auth / account
- [ ] Email verification flow
- [ ] Forgot-password / reset-password flow
- [ ] Account data export (GDPR art. 20)
- [ ] Refresh tokens + rotation
- [ ] 2FA (TOTP)

### Guilds
- [ ] `POST /guilds/{id}/promote/{account_id}` — MEMBER → OFFICER
- [ ] `POST /guilds/{id}/transfer/{account_id}` — leader handoff
- [ ] Application / invite flow (right now anyone can join a public guild)
- [ ] Chat pagination (hard-capped at 50 newest)
- [ ] Soft-delete / archive for messages

### Raids
- [ ] Scheduled raid auto-start (worker rotates when guild has no active raid)
- [ ] Difficulty tiers with scaled rewards
- [ ] Per-attempt cooldown (currently only gated by energy)
- [ ] Leaderboard endpoint (top-contributing guilds this week)

### LiveOps
- [ ] Scheduled future events (`starts_at` in the future — admin endpoint always uses `now`)
- [ ] Preview endpoint for upcoming / not-yet-started events
- [ ] `BONUS_GEAR_DROPS` kind is wired but has no seeded event or template helpers

### Content
- [ ] 10–20 more hero templates (currently 25)
- [ ] 5–10 more stages (currently 10)
- [ ] "Hard mode" campaign tier
- [ ] Boss-only hero templates (higher stats, meant for raids)
- [ ] Tutorial stage 0 / first-time walkthrough

### Combat
- [ ] More status effects (FREEZE, BURN, HEAL_BLOCK, REFLECT)
- [ ] Faction affinity / synergy bonuses ("3 DEVOPS on team = +10% ATK")
- [ ] AoE revive
- [ ] Combat log pruning (`log_json` size cap — see Sprint A)

### Infrastructure
- [ ] Redis-backed rate limiter (in-memory per-process; doesn't coordinate across replicas)
- [ ] Postgres end-to-end smoke (Docker; see Sprint C)
- [ ] Docker image build + push to a registry (Dockerfile exists, never built)
- [ ] Automated daily DB backup (SQLite volume → dated tarball on a schedule)
- [ ] Graceful shutdown — worker cancels + in-flight battles finish

### Observability (beyond slice 20)
- [ ] OpenTelemetry tracing (propagate request IDs into spans)
- [ ] Sentry error reporting
- [ ] Alerting thresholds documented (5xx rate, p99 latency)

### Anti-cheat / validation
- [ ] Per-account rate limit on `/battles` (not just per-IP)
- [ ] Cap arena attack attempts per hour
- [ ] Audit all endpoints for `hero_instance_id` ownership check
- [ ] Reject combat outcomes that couldn't happen (if client-authoritative layer ever gets added)

### Localization
- [ ] Message catalog (gettext-style) for user-visible strings
- [ ] Hero/skill-name translation fields on `HeroTemplate`
- [ ] `Accept-Language` header handling

### Payments
- [ ] Stripe integration (checkout session + webhook handling)
- [ ] `OfferBundle` table (premium shard bundles, starter packs)
- [ ] Purchase history / refund flow
- [ ] Anti-fraud basics (rate limit / device fingerprint)

### Frontend (beyond slice 21 minimal shell)
- [ ] Real SPA (React / Svelte / Vue)
- [ ] Battle-log playback animation
- [ ] Mobile-responsive layout
- [ ] PWA offline shell
- [ ] Native iOS / Android wrapper

---

## 🧪 Test matrix — coverage

### Covered ✅
- `test_combat.py` — deterministic resolver (seed=1312, hash-stable)
- `test_combat_unit.py` — scale_stat, level cap, power rating, strong-team-wins
- `test_gacha.py` — pity trigger, counter reset, 2000-pull distribution
- `test_active_sets.py` — LIFESTEAL heals, VIOLENT extra turns, control
- `test_api_core.py` — health, register+onboarding, full loop, dailies, 401s, shard depletion
- `test_guilds.py` — create, list, get, single-guild-per-account, succession, chat membership, kick
- `test_liveops_and_account.py` — endpoint shape, DOUBLE_REWARDS multiplier, delete email-match, leader-delete promotes
- `test_raids.py` — guild-required, full lifecycle, one-active-raid-per-guild
- `test_admin.py` — grant/ban/unban/promote, liveops CRUD, stats, audit log + filters, timed bans, worker auto-unban, CLI
- `test_observability.py` — /metrics shape + counters, X-Request-ID round-trip, static HTML markers
- `smoke_hero.py`, `smoke_gear.py`, `smoke_skill.py`, `smoke_arena.py`, `smoke_daily.py`, `smoke_cli.py`, `smoke_sets.py`, `smoke_ascend.py`, `smoke_sweep.py`, `smoke_web.py` — E2E against live server

### Gaps ❌
- [ ] `test_liveops_crud.py` — LiveOps events end-to-end against admin endpoints (partially covered in `test_admin.py`)
- [ ] Worker coverage — `_run_jobs()` tested directly for auto-unban, but not for daily-prune or raid-expiry
- [ ] Postgres end-to-end — full `pytest` against `postgresql+psycopg://…`
- [ ] Docker container smoke — `docker compose up --build`, hit `/healthz` + `/docs`
- [ ] `smoke_guild.py` E2E mirror of `test_guilds.py`
- [ ] `smoke_raid.py` E2E mirror of `test_raids.py`
- [ ] Load test — 100 concurrent players on `/battles` + `/summon` (k6 or locust)
- [ ] Long-running soak — 24 h with the worker task, verify no memory creep

---

## 🪧 Open design questions

- Should `special_level` cap stay at 5, or tier to 10 for more long-tail progression?
- Should raid bosses have unique skills? (Currently they reuse hero-template specials — reads fine but shallow.)
- How do we want to handle energy overflow for LiveOps grants? (Currently `compute_energy` preserves surplus above cap.)
- Server-side combat animations (timing info in log) or let the client pace it?
- Guild size — 30 max feels right for alpha; revisit after first cohort
- Arena: defense teams snapshotted at the moment they're set, or live-computed? Currently live.

---

## 🚚 Shipped — reference index

<details>
<summary>Completed slices (click to expand)</summary>

- Slice 1 — Project scaffold (uv, FastAPI, SQLAlchemy, SQLite)
- Slice 2 — Schema + core models (Account, HeroTemplate, HeroInstance, Stage, Battle)
- Slice 3 — Combat resolver v1 (turn meter, basic + special, 4 status effects)
- Slice 4 — Gacha with 50-pull pity, x1 / x10 endpoints
- Slice 5 — Campaign battles + energy + rewards + first-clear
- Slice 6 — CLI client (`play_hero.py`)
- Slice 7 — Gear drops + equip/unequip + combat bonus
- Slice 8 — Hero ascension (stars 1–5) + level-cap scaling
- Slice 9 — Sweep for cleared stages
- Slice 10 — Security + deployment (CORS, rate limit, JWT guard, Dockerfile, compose)
- Slice 11 — Content expansion (25 heroes, 10 stages, onboarding bonus)
- Slice 12 — Alpha README + pytest harness
- Slice 13 — Active gear sets (VIOLENT + LIFESTEAL)
- Slice 14 — Guilds + chat
- Slice 15 — Postgres readiness (extra dep, compose profile)
- Slice 16 — Background worker + LiveOps events (+ seeded Launch Week 2x)
- Slice 17 — Guild raids (shared HP, per-contrib rewards)
- Slice 18 — Account deletion (GDPR art. 17)
- Slice 19 — Admin panel (grant / ban / promote / liveops CRUD / stats)
- Slice 20 — Observability (Prometheus `/metrics`, JSON logs, `X-Request-ID`)
- Slice 21 — Minimal HTML client at `/app` (vanilla JS, no build step)
- Slice 62 — Migrations + test coverage for 19/20/21 (alembic admin columns, `test_admin.py`, `test_observability.py`)
- **Admin polish sprint** — CLI (`python -m app.admin`), `AdminAuditLog` + `/admin/audit`, timed bans (`banned_until` + worker auto-unban + lazy clear in deps)

</details>

---

## 📎 How to use this file

- Tick `[x]` when something lands; delete fully-resolved lines rather than leaving graveyard checkmarks (except in the "Shipped" index).
- New work goes under **Backlog** in its section, and gets pulled into **Next up** when it's being planned.
- Keep **Where we're at** current — it's the top-of-file status at a glance.
- Assume this file is authoritative for what's still open.
