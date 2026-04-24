# hero-proto — TODO & Test Reference

Living list. Tick items `[x]` as done. Add new ones at the bottom of the relevant section.

Last updated: 2026-04-24 (post Sprint A–D close-out).

---

## 📊 Where we're at

- **Backend:** 22 backend slices + admin polish + auth hardening + observability + payments + art wiring. `master` @ `5426eb7`, tree clean.
- **Auth:** refresh-token rotation w/ reuse detection, password reset, email verification, TOTP 2FA + recovery codes — all green in walkthrough.
- **Payments:** Stripe Checkout + webhooks wired; mock-payments mode for dev. Shop purchase round-trip passes.
- **Observability:** Prometheus `/metrics`, JSON logs, request IDs, Sentry (DSN-gated), worker supervisor w/ health telemetry.
- **Infra:** Redis-backed rate limiter (horizontal-scale ready). CI matrix runs on SQLite + Postgres per push.
- **Tests:** `pytest` green. Two automated acceptance scripts wrap everything:
  - `scripts/startup_check.py` — admin/operator health check (7 OK today)
  - `scripts/client_walkthrough.py` — 13-section end-to-end feature tour (all green today)
- **Docs:** `README.md`, `docs/RUNBOOK.md`, `docs/STARTUP_AND_TESTING.md`, `docs/ART_NEEDS.md` all current.
- **Frontend:** vanilla-JS shell at `/app` with integrated design-handoff battle UI + roster codex + Phaser replay. Functional but not a real SPA.
- **Art:** 50/51 SVGs patched to render standalone (designer tokens + heuristic class styles). One designer-styled file left alone.

### Verified green today (2026-04-24)

- Server starts, worker ticks, migrations + seed idempotent.
- `startup_check` — 7 OK, 2 optional warns (admin creds + Stripe probe both gated on env vars).
- `client_walkthrough` — auth / daily bonus / gacha / combat / energy refill / arena / daily quests / guilds / raids / shop / password reset / email verify / 2FA.

### Known papercuts still open

- **Postgres compose-stack smoke is runnable but unrun.** `scripts/postgres_stack_validate.sh` brings up the stack and runs both acceptance scripts against it, but needs Docker Desktop up — once someone runs it green it's a trust-but-verify step before calling Postgres "done."
- **Frontend is a bare shell.** Works for smoke-testing; not shippable to real users.

---

## 🎯 Next up — ranked candidate sprints

Each sprint is sized to be shippable in one session. Pick one; don't interleave.

### A. Frontend polish
The dashboard works; nobody wants to look at it. Biggest perceived-quality lift per hour.
- [ ] CSS pass on `/app/*` (currently unstyled vanilla HTML)
- [ ] Loading states + error toasts (right now failures are silent `alert()` boxes)
- [ ] Mobile-responsive layout
- [ ] Or: rewrite as a real SPA (React / Svelte) — bigger bet; needs a build step

### B. Anti-cheat depth
One layer shipped (per-account battle rate limit). More to add.
- [ ] Cap arena attack attempts per hour (separate from /battles bucket)
- [ ] Audit all endpoints for `hero_instance_id` ownership check
- [ ] Reject implausible combat outcomes (if a client-authoritative layer is ever added)
- [ ] Per-IP guild-message rate limit to stop chat flooding

### C. Deploy pipeline
Dockerfile + compose exist; nothing's been pushed or deployed.
- [ ] Run `scripts/postgres_stack_validate.sh` once green (trust-but-verify the Postgres path)
- [ ] Build + push Docker image to a registry (Fly / GHCR / ECR)
- [ ] Pick a hosted target (Fly / Railway / Render / plain VM) and do a first deploy
- [ ] Automated daily DB backup (volume → dated tarball on a schedule)
- [ ] Graceful shutdown — worker cancels + in-flight battles finish

### D. Raid depth
Raids work; they're shallow.
- [ ] Scheduled raid auto-start (worker rotates when guild has no active raid)
- [ ] Per-attempt cooldown (currently only gated by energy)
- [ ] Leaderboard endpoint (top-contributing guilds this week)
- [ ] Unique boss-only specials (dedicated templates now exist, still use hero specials)

### E. Observability next steps
- [ ] OpenTelemetry tracing (propagate request IDs into spans)
- [ ] Alerting thresholds documented (5xx rate, p99 latency)
- [ ] Dashboard screenshots / PromQL cookbook in `RUNBOOK.md`

**Recommendation:** ship **A** next — the backend is stable enough that the next real-user bottleneck is how the thing looks. **C** is the right choice if the goal is "put it in front of external testers" rather than "make it prettier."

---

## 🚧 Backlog — everything else

### Admin tooling
- [ ] Ban should invalidate existing JWTs (Sprint A)
- [ ] Admin UI over the existing `/admin/*` endpoints (currently curl-only)

### Auth / account
- [ ] Account data export (GDPR art. 20)
- [ ] Login history / active sessions list
- [ ] Device fingerprinting for refresh-token anomaly detection

### Guilds
- [ ] Promote / transfer endpoints (Sprint B)
- [ ] Application / invite flow (Sprint B)
- [ ] Soft-delete / archive for messages
- [ ] Per-guild achievements / milestones

### Raids
- [ ] Scheduled raid auto-start (worker rotates when guild has no active raid)
- [ ] Per-attempt cooldown (currently only gated by energy)
- [ ] Leaderboard endpoint (top-contributing guilds this week)
- [ ] Boss-only unique specials

### LiveOps
- [ ] Scheduled future events (`starts_at` in the future — admin endpoint always uses `now`)
- [ ] Preview endpoint for upcoming / not-yet-started events
- [ ] Seed event for `BONUS_GEAR_DROPS` kind

### Content
- [ ] See Sprint D

### Combat
- [ ] More status effects (FREEZE, BURN, HEAL_BLOCK, REFLECT)
- [ ] Faction affinity / synergy bonuses ("3 DEVOPS on team = +10% ATK")
- [ ] AoE revive
- [ ] Combat log pruning (Sprint A)

### Infrastructure
- [ ] Postgres end-to-end smoke (Sprint C)
- [ ] Docker image build + push to a registry (Dockerfile exists, never built)
- [ ] Automated daily DB backup (SQLite volume → dated tarball on a schedule)
- [ ] Graceful shutdown — worker cancels + in-flight battles finish
- [ ] Deploy target picked (Fly / Railway / Render / plain VM)

### Observability
- [ ] OpenTelemetry tracing (propagate request IDs into spans)
- [ ] Alerting thresholds documented (5xx rate, p99 latency)
- [ ] Dashboard screenshots in `RUNBOOK.md`

### Anti-cheat / validation
- [ ] Per-account rate limit on `/battles` (Sprint A)
- [ ] Cap arena attack attempts per hour
- [ ] Audit all endpoints for `hero_instance_id` ownership check
- [ ] Reject combat outcomes that couldn't happen (if client-authoritative layer ever gets added)

### Localization
- [ ] Message catalog (gettext-style) for user-visible strings
- [ ] Hero/skill-name translation fields on `HeroTemplate`
- [ ] `Accept-Language` header handling

### Payments
- [ ] `OfferBundle` table (premium shard bundles, starter packs)
- [ ] Purchase history / refund flow UI
- [ ] Anti-fraud basics (velocity limits, device fingerprint)
- [ ] Subscriptions / monthly pass

### Frontend
- [ ] CSS + loading/error states (Sprint E)
- [ ] Mobile-responsive layout
- [ ] Real SPA (React / Svelte / Vue)
- [ ] PWA offline shell
- [ ] Native iOS / Android wrapper

---

## 🧪 Test matrix — coverage

### Covered ✅
- Unit: `test_combat.py`, `test_combat_unit.py`, `test_gacha.py`, `test_active_sets.py`
- API: `test_api_core.py`, `test_guilds.py`, `test_liveops_and_account.py`, `test_raids.py`, `test_admin.py`, `test_observability.py`
- Scripts: `smoke_hero.py`, `smoke_gear.py`, `smoke_skill.py`, `smoke_arena.py`, `smoke_daily.py`, `smoke_cli.py`, `smoke_sets.py`, `smoke_ascend.py`, `smoke_sweep.py`, `smoke_web.py`
- Acceptance: `scripts/startup_check.py`, `scripts/client_walkthrough.py` (13 sections)
- CI: SQLite + Postgres matrix per push

### Gaps ❌
- [ ] Full `pytest` + E2E smokes against live compose-Postgres (not just CI) — Sprint C
- [ ] Docker container smoke — `docker compose up --build`, hit `/healthz` + `/docs`
- [ ] `smoke_guild.py` / `smoke_raid.py` E2E mirrors of the unit tests
- [ ] Load test — 100 concurrent players on `/battles` + `/summon` (k6 or locust)
- [ ] Long-running soak — 24 h with the worker task, verify no memory creep
- [ ] Stripe webhook signature round-trip against real `stripe listen` (tested with mocks, not the CLI)

---

## 🪧 Open design questions

- Should `special_level` cap stay at 5, or tier to 10 for more long-tail progression?
- Should raid bosses have unique skills? (Currently they reuse hero-template specials — reads fine but shallow.)
- How do we want to handle energy overflow for LiveOps grants? (Currently `compute_energy` preserves surplus above cap.)
- Server-side combat animations (timing info in log) or let the client pace it?
- Guild size — 30 max feels right for alpha; revisit after first cohort.
- Arena: defense teams snapshotted at the moment they're set, or live-computed? Currently live.
- Frontend: real SPA vs keep polishing the vanilla shell? SPA means a build step + deploy story.

---

## 🚚 Shipped — reference index

<details>
<summary>Completed slices (click to expand)</summary>

**Foundations**
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
- Slice 62 — Migrations + test coverage for 19/20/21

**Admin polish sprint** — CLI (`python -m app.admin`), `AdminAuditLog` + `/admin/audit`, timed bans (`banned_until` + worker auto-unban + lazy clear in deps)

**Auth hardening sprint**
- Password reset flow with dev-mode bypass
- Email verification flow
- Email sender adapter (SMTP + console + file sinks)
- Refresh tokens with rotation + reuse-detection
- 2FA (TOTP) — enroll, confirm, disable, login challenge, verify
- 2FA recovery codes — lost-phone backup

**Observability / reliability sprint**
- Sentry error reporting — DSN-gated, filters expected 4xx
- Worker supervisor — respawn + health telemetry on `/worker/status`
- Redis-backed rate limiter — horizontal-scale ready
- `docs/RUNBOOK.md` — operator quickstart

**Economy + arena sprint**
- Daily login bonus / streak
- Daily quest variety: CLEAR_HARD_STAGE + RAID_DAMAGE + SPEND_GEMS
- Gem sink — energy refill + SPEND_GEMS quest activation
- Arena matchmaking — rating-proximity with progressive widening
- Arena match replay endpoint + UI links
- Guild chat — keyset pagination ("load older" button)

**Payments**
- Stripe Checkout + webhook handling
- Shop products + purchases + mock-payments for dev
- DELETE /me audit + SQLite FK enforcement

**Content / UX**
- Design-handoff battle UI integration (setup / replay / roster)
- 50 SVGs patched to render standalone (scripts/patch_art_styles.py)
- Admin analytics overview endpoint
- API audit: cap unbounded list endpoints + conventions doc

**Sprint A–D close-out (2026-04-24)**
- Sprint A: JWT token-version on ban (already shipped earlier), combat log pruning (already shipped), per-account /battles rate limit (new)
- Sprint B: guild promote/demote/transfer/apply/accept/reject/withdraw — all shipped + unit + smoke coverage
- Sprint C: `scripts/postgres_stack_validate.sh` — one-shot compose-Postgres smoke (runs on demand)
- Sprint D: +10 heroes (7 roster + 3 raid-boss templates), +6 stages (tutorial stage 0 + orders 11–15), +1 BONUS_GEAR_DROPS liveops seed

**Testing / docs**
- CI on every push with Postgres matrix
- `scripts/startup_check.py` — admin-side health check
- `scripts/client_walkthrough.py` — 13-section client feature tour
- `docs/STARTUP_AND_TESTING.md` — operator runbook

</details>

---

## 📎 How to use this file

- Tick `[x]` when something lands; delete fully-resolved lines rather than leaving graveyard checkmarks (except in the "Shipped" index).
- New work goes under **Backlog** in its section, and gets pulled into **Next up** when it's being planned.
- Keep **Where we're at** current — it's the top-of-file status at a glance.
- Assume this file is authoritative for what's still open.
