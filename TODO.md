# hero-proto — TODO & Test Reference

Living list. Tick items `[x]` as done. Add new ones at the bottom of the relevant section.

Last updated: 2026-04-23.

---

## 🔥 In flight (current sprint)

- [ ] **Slice 20 — Observability**
  - [ ] Prometheus `/metrics` endpoint (counters: requests_total, battles_total, summons_total; histogram: request_duration_seconds)
  - [ ] JSON log formatter enabled via `HEROPROTO_JSON_LOGS=1`
  - [ ] `X-Request-ID` middleware (generate if absent, echo back, thread into log context)
  - [ ] Add `prometheus-client` to deps
  - [ ] `test_observability.py` covering `/metrics` shape + request-id round-trip

- [ ] **Slice 21 — Minimal HTML client**
  - [ ] `app/static/index.html` single-page vanilla JS (no build step)
  - [ ] Tabs / sections: Login · Me · Roster · Stages · Daily · Arena · Guild
  - [ ] Token stored in `localStorage` as `heroproto_jwt`
  - [ ] Mount `StaticFiles` at `/app` in `app/main.py`
  - [ ] Homepage `GET /` redirects to `/app/` when no JWT, otherwise dashboard
  - [ ] `smoke_web.py` — simple `httpx` GET that asserts the HTML loads and has expected markers

- [ ] **Slice 62 — Migrations + test coverage for 19/20/21**
  - [ ] Alembic autogen for admin columns (`is_admin`, `is_banned`, `banned_reason`) with `server_default` so existing rows backfill
  - [ ] `test_admin.py` — grant, ban/unban, promote, liveops create/cancel, stats endpoint, non-admin 403
  - [ ] Banned user's existing token is rejected (401/403)
  - [ ] Re-run full pytest + 10 E2E smokes green

---

## 🚧 Backlog — known gaps & follow-ups that came up during dev

### Admin tooling
- [ ] CLI: `uv run python -m app.admin promote <email>` for bootstrapping the first admin without DB shell
- [ ] Admin audit log table (who banned/granted what, when, to whom)
- [ ] Timed bans (`banned_until: datetime` + worker auto-unbans)
- [ ] Ban should invalidate existing JWTs (currently relies on the 403 in the dep — token is still technically "valid" until expiry)
- [ ] Admin "broadcast announcement" — creates a pinned MOTD visible on `GET /me` or its own endpoint

### Auth / account
- [ ] Email verification flow
- [ ] Forgot-password / reset-password flow
- [ ] Account data export (GDPR art. 20)
- [ ] Refresh tokens + rotation
- [ ] 2FA (TOTP)

### Guilds
- [ ] `POST /guilds/{id}/promote/{account_id}` — leader can promote MEMBER → OFFICER
- [ ] `POST /guilds/{id}/transfer/{account_id}` — leader hands off without leaving
- [ ] Guild application / invite flow (right now anyone can join a public guild)
- [ ] Guild chat pagination (currently hard-capped at 50 newest)
- [ ] Soft-delete / archive for messages

### Raids
- [ ] Scheduled raid auto-start (worker picks from a rotation when guild has no active raid)
- [ ] Raid difficulty tiers with scaled rewards
- [ ] Per-attempt cooldown (currently only gated by energy)
- [ ] Raid leaderboard endpoint (top-contributing guilds this week)

### LiveOps
- [ ] Scheduled future events (not just "start now" but `starts_at` can be in the future — partially supported; admin endpoint always uses `now`)
- [ ] Event preview endpoint for upcoming / not-yet-started events
- [ ] `BONUS_GEAR_DROPS` kind is wired but has no default seeded event or admin template helpers

### Content
- [ ] 10–20 more hero templates (currently 25)
- [ ] 5–10 more stages (currently 10)
- [ ] "Hard mode" campaign tier
- [ ] Boss-only hero templates (higher stats, meant for raids)
- [ ] Tutorial stage 0 / first-time-user walkthrough

### Combat
- [ ] More status effects (FREEZE, BURN, HEAL_BLOCK, REFLECT)
- [ ] Faction affinity / synergy bonuses ("3 DEVOPS on team = +10% ATK")
- [ ] AoE revive
- [ ] Combat log pruning (log_json can get large on long battles — cap entries server-side)

### Infrastructure
- [ ] Redis-backed rate limiter (current is in-memory per-process; doesn't coordinate across replicas)
- [ ] Postgres smoke test (Docker isn't available locally; verify on a host that has it)
- [ ] Docker image build + push to a registry (Dockerfile exists, never built)
- [ ] Automated daily DB backup (SQLite volume → dated tarball on a schedule)
- [ ] Graceful shutdown — worker cancels + in-flight battles finish

### Observability (beyond slice 20)
- [ ] OpenTelemetry tracing (propagate request IDs into spans)
- [ ] Sentry error reporting
- [ ] Alerting thresholds documented (5xx rate, p99 latency)

### Anti-cheat / validation
- [ ] Server-side rate-limit per account (not just per IP) on `/battles`
- [ ] Detect impossible teams (hero_instance_id owned by account_id check is already there — audit other endpoints)
- [ ] Cap arena attack attempts per hour
- [ ] Validate stage_id is cleared before sweep (already done — reference test)
- [ ] Reject combat outcomes that couldn't happen (if client-authoritative layer ever gets added)

### Localization
- [ ] Message catalog (gettext-style) for user-visible strings
- [ ] Hero name / skill name translation fields on `HeroTemplate`
- [ ] `Accept-Language` header handling

### Payments
- [ ] Stripe integration (checkout session creation, webhook handling)
- [ ] `OfferBundle` table (premium shard bundles, starter packs)
- [ ] Purchase history / refund flow
- [ ] Anti-fraud basics (rate limit / device fingerprint)

### Frontend (beyond slice 21 minimal)
- [ ] Real SPA (React / Svelte / Vue)
- [ ] Battle animation playback from log
- [ ] Mobile-responsive layout
- [ ] PWA offline shell
- [ ] Native iOS / Android wrapper

---

## 🧪 Test matrix — what's covered vs. what's not

### Covered ✅
- [x] `test_combat.py` — deterministic combat resolver (seed=1312, hash-stable)
- [x] `test_combat_unit.py` — scale_stat, level cap, power rating, strong-team-wins
- [x] `test_gacha.py` — pity trigger, counter reset, distribution sanity over 2000 pulls
- [x] `test_active_sets.py` — LIFESTEAL heal events, VIOLENT extra turns, control (no flag)
- [x] `test_api_core.py` — health, register grants starter+onboarding, full loop, dailies, 401s, shard depletion
- [x] `test_guilds.py` — create, list, get, single-guild-per-account, leader succession, chat membership, leader kick
- [x] `test_liveops_and_account.py` — endpoint shape, DOUBLE_REWARDS multiplier applied, delete email-match, leader delete promotes
- [x] `test_raids.py` — guild-required, full lifecycle (start → hammer → defeat → second-attack 409), one-active-raid-per-guild
- [x] `smoke_hero.py` — full end-to-end over HTTP
- [x] `smoke_gear.py` — drop, equip, unequip stat delta
- [x] `smoke_skill.py` — skill-up consume dupes, reject self-feed, reject wrong-template
- [x] `smoke_arena.py` — defense set, opponents, attack, leaderboard
- [x] `smoke_daily.py` — 3 rolled, idempotent, progression, claim, double-claim 409
- [x] `smoke_cli.py` — headless CLI client exercise
- [x] `smoke_sets.py` — passive set activates, stat bonus visible
- [x] `smoke_ascend.py` — 1★ → 2★, fodder consumed, wrong count rejected
- [x] `smoke_sweep.py` — pre-clear rejected, post-clear sweep, count cap

### Gaps ❌
- [ ] `test_admin.py` — nothing yet for the admin router
- [ ] `test_observability.py` — Prometheus format + request-id plumbing
- [ ] `test_liveops_crud.py` — admin creates/cancels a LiveOps event end-to-end
- [ ] Worker coverage — trigger `_run_jobs()` directly in a test; confirm old dailies pruned and expired raids flipped
- [ ] Ban flow — banned user's subsequent request returns 403
- [ ] Postgres end-to-end — run the pytest suite against a `postgresql+psycopg://` URL
- [ ] Docker container smoke — `docker compose up --build`, healthz, hit `/docs`
- [ ] `smoke_guild.py` E2E mirror of `test_guilds.py` against the live server
- [ ] `smoke_raid.py` E2E mirror of `test_raids.py` against the live server
- [ ] `smoke_web.py` — GET `/` and `/app/index.html` return 200 with expected markers
- [ ] Load test — 100 concurrent players hitting `/battles` and `/summon` (k6 or locust)
- [ ] Long-running soak — 24 h with the worker task, verify no memory creep

---

## 🪧 Open design questions

- [ ] Should `special_level` cap stay at 5, or tier to 10 for more long-tail progression?
- [ ] Should raid bosses have unique skills (right now they reuse hero template specials — reads fine but shallow)?
- [ ] How do we want to handle energy overflow for LiveOps grants? (currently `compute_energy` preserves surplus above cap)
- [ ] Do we want server-side combat animations (timing info in log) or let the client pace it?
- [ ] Guild size — 30 max feels right for the alpha; revisit after first cohort
- [ ] Arena: should defense teams be snapshotted at the moment they're set (stats frozen) or live-computed (risky if attacker has seen your team yesterday)? Currently live.

---

## 🚚 Done — reference for what's shipped

<details>
<summary>Completed slices (click to expand)</summary>

- [x] Slice 1 — Project scaffold (uv, FastAPI, SQLAlchemy, SQLite)
- [x] Slice 2 — Schema + core models (Account, HeroTemplate, HeroInstance, Stage, Battle)
- [x] Slice 3 — Combat resolver v1 (turn meter, basic + special, 4 status effects)
- [x] Slice 4 — Gacha with 50-pull pity, x1 / x10 endpoints
- [x] Slice 5 — Campaign battles + energy + rewards + first-clear
- [x] Slice 6 — CLI client (`play_hero.py`)
- [x] Slice 7 — Gear drops + equip/unequip + combat bonus
- [x] Slice 8 — Hero ascension (stars 1–5) + level cap scaling
- [x] Slice 9 — Sweep for cleared stages
- [x] Slice 10 — Security + deployment (CORS, rate limit, JWT guard, Dockerfile, compose)
- [x] Slice 11 — Content expansion (25 heroes, 10 stages, onboarding bonus)
- [x] Slice 12 — Alpha README + pytest harness
- [x] Slice 13 — Active gear sets (VIOLENT + LIFESTEAL)
- [x] Slice 14 — Guilds + chat
- [x] Slice 15 — Postgres readiness (extra dep, compose profile)
- [x] Slice 16 — Background worker + LiveOps events (+ seeded Launch Week 2x)
- [x] Slice 17 — Guild raids (shared HP, per-contrib rewards)
- [x] Slice 18 — Account deletion (GDPR art. 17)
- [x] Slice 19 — Admin panel (grant / ban / promote / liveops CRUD / stats)

</details>

---

## 📎 How to use this file

- Tick `[x]` when something lands.
- Move finished items from "In flight" to "Done".
- New backlog items go under "Backlog" or "Test matrix gaps" depending on type.
- Assume this file is authoritative for what's still open — keep it current.
