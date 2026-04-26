# hero-proto — TODO & Test Reference

Living list. Tick items `[x]` as done. Add new ones at the bottom of the relevant section.

Last updated: 2026-04-24 (post Phase 1 close-out).

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

## 🗺️ Product direction (from play-testing 2026-04-24)

Feedback from the first UI walkthrough — long-term vision, not next-sprint work. Captured so nothing gets dropped.

### Combat / gameplay
- **Battle feels like a spectator right now.** Player has no control once the sim starts. Aim: skill-based combat where players can win by playing well. Path:
  - Ability targeting during a fight (click enemy to focus, pick special target)
  - Turn timer / active pause like CRPGs, or tap-timing like Honkai
  - **Auto-battle** becomes a QoL unlock, not the default — sold in the shop as a convenience, never as pay-to-win
- **Melee vs ranged split** — introduce a `ranged` attack channel alongside the existing `basic`. Ranged covers magic users; may need a `mana` resource or rename/repurpose `special_cooldown`.
- **Hail-mary mechanic** — at ≤5% HP, heroes can trigger a one-shot desperation ability (flavor varies by role/faction). Gives late-fight drama.

### Art / presentation
- Battle viewer needs animated actors. Reference: *Shogun / ShoHo* small-character style with short attack loops.
- **Stick figures are fine as placeholders** — better than silhouettes. Can animate the same rig across heroes until real art lands.
- Current SVG portraits stay on roster/replay cards; battle stage needs its own animated layer.

### Roster / progression (meta loop)
- Per-hero **equipment panels**: weapon + armor + accessories. Currently we have abstract `Gear` but no per-slot weapon/armor semantics.
- **Skills subtab** per hero — level up each skill independently (currently we only have `special_level`)
- **Special abilities tab** — the named signature move with upgrade paths
- Roster UX has to **make players *want* to upgrade** — visible power deltas, next-unlock teasers, star-up previews. Right now the page is a JSON dump.
- **Dedupe summons visually** — group the same template together rather than listing ten identical "Jaded Intern" cards.

### Summon changes
- On duplicate pull of a hero the player already owns, **roll per-stat variance** (+10 / -5 or similar) so owned copies aren't identical — adds rolls worth chasing.
- **Rarity-separated tabs** in the roster/summon view: Common / Uncommon / Rare / Epic / Legendary / **Myth**.
- **Myth tier** = event-only (holidays, anniversaries, LiveOps windows). Never in the normal pool.

### Stages / team picker
- Team-selection UX is rough. Wins:
  - **Saved team presets** — "Arena Team", "Campaign Team", "Raid Team" (QoL)
  - One-click "use last team" button
  - Recommended-power hinting next to team power
- **Auto-team** (best power) is a QoL unlock alongside auto-battle.

### Monetization model
- Reference: **Path of Exile 2** shop — cosmetic / QoL / stash-tab style, *never* direct power.
- Gems → QoL packs (auto-battle, saved presets, extra roster slots, cosmetic frames, emotes).
- Keep F2P viable: all progression paths reachable without spending.
- Existing Stripe + mock-payments pipeline already works; new SKUs are a content problem, not an engineering one.

---

## 🎯 Phase 2 preview — next big arc

Phase 1 is done. The product is now genuinely playable for a new user — tutorial flow, visual roster, team presets, dedicated Summon tab, starter pack. Next arc is Phase 2 ("Feels like a real game") per `docs/PRD.md § 7`:

- Hero detail depth: weapon/armor/accessory slots, skill tree UI, star-up flow, next-upgrade previews
- Event content: Myth-tier hero wired end-to-end, scheduled future LiveOps, stat variance on dupes
- Analytics: PostHog self-hosted, 12 events instrumented, funnels — **shipped 2026-04-26 (Phase 2.3 ✅)**: graceful wrapper in `app/analytics.py`, 12 events instrumented (register/login/summon_x1/x10/stage_start/stage_clear/first_clear/arena_attack/raid_attack/purchase_start/purchase_complete/daily_bonus_claim), 11 mocked-client tests, RUNBOOK §Analytics with Cloud-first bring-up + funnel + dashboard recipes, `scripts/verify_analytics.py` smoke tester, `scripts/posthog_dashboard.json` 10-insight starter dashboard import. **Last step (ops):** set `HEROPROTO_POSTHOG_API_KEY` in prod env, run verify_analytics from staging, import dashboard, run client_walkthrough — covers the Phase 2 acceptance criteria.
- Store expansion: PoE2-style QoL SKUs, Apple StoreKit 2 receipt verification, Google Play Billing
- Balance tooling: Jupyter notebook with gacha EV / DPS curves / arena rating convergence
- Story campaign + account-level XP + Exile as default faction (Phase 2.5)

Duration: 3-4 weeks. New deps: PostHog, app-store-server-library, google-play-billing-validator, numpy/pandas/Jupyter.

---

## 🎯 Legacy sprint backlog (pre-PRD scoping)

Each sprint is sized to be shippable in one session. Pick one; don't interleave.

### A. Frontend polish
The dashboard works; nobody wants to look at it. Biggest perceived-quality lift per hour.
- [ ] CSS pass on `/app/*` (currently unstyled vanilla HTML)
- [x] Error toasts — `app/static/toast.js` provides `toast.error/success/info(msg)`; bottom-center stack, color-coded by kind, auto-dismiss (errors 5s, others 3.5s), tap-to-dismiss; replaced 9 `alert()` callsites in friends/stages/story partials + battle-setup/roster static pages
- [x] Loading states — shared `.skeleton` / `.skeleton-line` / `.skeleton-grid` utilities in shell.html + initial `#content` placeholder + reuse in account/raids partials. Per-section refinement (every partial gets its own shimmer skeleton matching its layout) is still open as a polish pass.
- [ ] Mobile-responsive layout
- [ ] Or: rewrite as a real SPA (React / Svelte) — bigger bet; needs a build step

### B. Anti-cheat depth
One layer shipped (per-account battle rate limit). More to add.
- [x] Cap arena attack attempts per hour — `arena_attack_per_minute_per_account=20` enforced via `enforce_arena_rate_limit`
- [x] Audit all endpoints for `hero_instance_id` ownership check — 7 guard tests in `test_cross_account_ownership.py`
- [ ] Reject implausible combat outcomes (still blocked on a client-authoritative layer; not actionable yet)
- [x] Per-IP guild-message rate limit — `enforce_guild_message_ip_rate_limit` in chat dependencies, Redis-backed under horizontal scale

### C. Deploy pipeline
Dockerfile + compose exist; nothing's been pushed or deployed.
- [ ] Run `scripts/postgres_stack_validate.sh` once green (trust-but-verify the Postgres path)
- [ ] Build + push Docker image to a registry (Fly / GHCR / ECR)
- [ ] Pick a hosted target (Fly / Railway / Render / plain VM) and do a first deploy
- [x] Automated daily DB backup — `scripts/backup_db.sh` handles SQLite (sqlite3 .backup + gzip) and Postgres (pg_dump custom format), date-stamped names, RETAIN-based pruning, run from cron/systemd-timer
- [x] Graceful shutdown — worker cancels + in-flight battles finish (lifespan handles it; documented in RUNBOOK with uvicorn flag recommendations)

### D. Raid depth ✅ done (2026-04-25)
Raids work; they're shallow.
- [x] Scheduled raid auto-start — `_auto_rotate_raids()` in `app/worker.py` (already shipped)
- [x] Per-attempt cooldown — `RAID_ATTEMPT_COOLDOWN_SECONDS = 600` enforced in `attack_raid` (already shipped)
- [x] Leaderboard endpoint — `GET /raids/leaderboard?days=7&limit=25`, public, in `app/routers/raids.py` (already shipped)
- [x] Unique boss-only specials — new `BOSS_PHASE` special type; 3 raid bosses re-tuned to use it with HEAL_BLOCK / FREEZE / BURN + self REFLECT/ATK_UP. See "Sprint D close (2026-04-25)" below.

### E. Observability next steps
- [ ] OpenTelemetry tracing (propagate request IDs into spans)
- [x] Alerting thresholds documented — 9 alerts in `docs/RUNBOOK.md` (5xx rate, p99 latency, worker stalls, 429 bursts, purchase failures, webhook signature failures, etc.) with severity tags + PromQL
- [x] PromQL cookbook in `RUNBOOK.md` — 11 copy-paste queries for the standard Grafana panels + 7-row dashboard layout. Screenshots TBD (need real prod traffic to capture)

**Recommendation:** ship **A** next — the backend is stable enough that the next real-user bottleneck is how the thing looks. **C** is the right choice if the goal is "put it in front of external testers" rather than "make it prettier."

### F. Roster / summon UX overhaul (from play-testing)
Medium-sized but the highest-leverage UX work right now. See Product Direction section above for full context.
- [x] Group duplicate heroes in roster — `/app/partials/roster` groups by `template_code`, exposes `dupe_count` + `instance_ids`; rendered as one card per template with count badge
- [x] Rarity-separated tabs in roster — tab row with `data-rarity` filter, Common→Myth, sticky active-state in `partials/roster.html`
- [x] Pretty x10 summon result — sorted by rarity desc, header summarises best pull, grid of rarity-bordered cards, plays the highest-rarity sfx cue
- [x] Per-hero detail page — slide-up sheet via `#hero-detail-overlay` in roster partial; stats / skill level / gear / next-star preview all in there
- [x] Saved team presets — `TeamPreset` model + full CRUD at `/me/team-presets` (`tests/test_team_presets.py`); paid unlock gating remains a future product call
- [x] "Use last team" — `GET /me/last-team` derives from most recent winning battle, falls back to most recent any-result, then to empty

### H. PWA ✅ shipped
- [x] `app/static/manifest.webmanifest`
- [x] Service worker at `/app/static/sw.js` — versioned cache, shell cache-first, /me & friends network-only
- [x] Apple touch icons + meta tags in `templates/base.html`
- [x] Service worker registered from dashboard entry
- [ ] Field-test: install on Android Chrome, install on iOS Safari, confirm icon + splash + offline-launch — **manual QA pass, not automatable**

### G. Combat depth (from play-testing)
Design-first sprint — probably 2-3 iterations before it's good. Reference games listed in Product Direction.
- [ ] Melee / ranged attack split (extend `basic_mult` model → `melee_mult` + `ranged_mult`)
- [ ] Mana or spell-point resource for ranged/magic heroes
- [x] Hail-mary ability at ≤5% HP — `_maybe_hail_mary` end-of-turn check, role-flavored (ATK 'Last Stand' 3× burst / DEF 'Hold The Line' AOE+stun / SUP "You're Welcome" AOE_HEAL+ATK_UP). One-shot per battle. New `HAIL_MARY` event type rendered with gold flash + camera shake + named banner. Per-faction overrides hookable via template `hail_mary` field later.
- [ ] Player control during battle (target selection / turn pause)
- [ ] Animated actor layer for battle viewer (stick figures → real art)
- [ ] Auto-battle as a paid QoL unlock, not the default

**Monetization tone lock:** PoE2-style — cosmetics + QoL. No stat-boosting shop items, no gacha whales fast-tracking power. Stripe pipeline stays; only the SKU catalog changes.

---

## 📱 Mobile strategy

Architecture is already native-friendly — every player feature is an HTTP JSON API, the web UI is just one client. Four paths, ranked by realism:

1. **PWA** (half-day) — installable from browser, home-screen icon, offline shell. No store listing, no native IAP.
2. **Capacitor wrapper** (1–2 weeks) — same web UI packaged as `.apk` / `.ipa`, submitted to both stores. Adds Apple IAP + Google Play Billing receipt-verification to `shop.py` as separate payment adapters alongside Stripe.
3. **React Native / Flutter** (months) — native UI, keep backend. Second codebase to maintain. Only if combat/animation layer outgrows mobile browsers.
4. **Fully native** (Swift + Kotlin) — overkill for this team.

**Recommendation:** ship Sprint H (PWA) first, then Capacitor when ready to submit to stores. `DELETE /me` + 2FA + refresh-token rotation + the audit log already satisfy Apple/Google store policy requirements for data handling.

---

## 🎨 Design-AI work queue (no repo access needed)

Work the design AI can do without committing code. Outputs land as SVG / PNG / Lottie / Figma / markdown — pasted into the repo by hand after review. Ranked by how much they unblock ongoing sprints.

### High leverage
- [ ] **Stick-figure battle animation sprite sheets** — unblocks Sprint G. Short loops (4–8 frames): idle, melee attack, ranged attack, hit reaction, death, special trigger. SVG sprite sheet or Lottie JSON. One rig per role (ATK/DEF/SUP).
- [ ] **App icon + maskable PWA icons** — unblocks Sprint H. 192×192, 512×512, maskable-safe (80% inner keep-clear), 1024×1024 for Apple touch icon.
- [ ] **Roster card redesign mockups** — current is a list, we want rarity-tabbed grid with faction/role/power/upgrade-teaser per hero. Figma or annotated PNG.
- [ ] **Shop page mockups — PoE2-style** — layout for gem packs, QoL packs, cosmetic frames, seasonal offers. Tone: premium/optional, not FOMO.

### Medium leverage
- [ ] **Missing hero portraits** — roster currently has 35 heroes; any generic/placeholder slots that need art. Request: faction-tinted backgrounds, role-suggestive poses.
- [ ] **Stage background set** — 32 stages need environmental variety (server room / cubicle / boss office / cable hell / boardroom / data center / storage closet etc.). SVG or 1024×576 PNG, dark palette compatible.
- [ ] **Raid boss art** — 3 boss templates (Legacy Colossus, C-Suite Hydra, Chaos Dragon) need hero-card art *and* an animated hit-reaction layer for the raid fight view.
- [ ] **Faction badges 2.0** — current are fine; a signed-off final palette would let the UI stop tuning colors ad-hoc.

### Low leverage / nice-to-have
- [ ] **Loading skeleton designs** — generic shimmer utility shipped (`.skeleton`/`.skeleton-line`/`.skeleton-grid` in shell.html); this row is about per-section skeletons that match each partial's actual layout (me / roster / battle setup / shop).
- [ ] **Empty-state illustrations** — text-and-emoji placeholders shipped via the shared `.empty-state` component; this row is now about *upgrading the icon* to a real illustration per state (arena/guild/raid/heroes/mailbox/etc.).
- [ ] **Hero lore snippets** — 2–3 sentence backstory per template; names exist, flavor doesn't.
- [ ] **Logo / wordmark** — current header is plain text; a simple mark would help branding.
- [ ] **Stage tier icons** — NORMAL / HARD / future NIGHTMARE tier badges.
- [ ] **Achievement art** — once achievements exist, badges for first-clear-stage-X, guild-raid-wins, etc.

### Explicitly NOT for design AI
- Anything touching Python / SQL / migrations / tests
- API schema changes
- CI/CD pipeline
- Security / auth flow

Output format for everything on this list: **paste the final file(s) back here in chat**; we'll drop them into `app/static/` manually. The design session that tried to commit directly couldn't, and that workflow held us up for a week.

---

## 🚧 Backlog — everything else

### Admin tooling
- [x] Ban should invalidate existing JWTs — `admin.ban()` bumps `token_version`, `deps.get_current_account` rejects stale tokens, covered by `tests/test_admin.py::test_ban_revokes_outstanding_jwt_via_token_version`
- [ ] Admin UI over the existing `/admin/*` endpoints (currently curl-only)

### Auth / account
- [x] Account data export (GDPR art. 20) — `GET /me/export`, e2d2ff5
- [x] Login history / active sessions list — `GET /me/sessions` + revoke endpoints, e2d2ff5
- [x] Device fingerprinting for refresh-token anomaly detection — `fingerprint_hash` (sha256 of UA|IP) on RefreshToken, compared on rotation. Mismatch logs `auth.refresh` warning + bumps `refresh_token_anomaly_total` Prometheus counter; never auto-revokes (legit users roam, browsers update). 4 new tests cover persist + match + mismatch + null-legacy paths.

### Guilds
- [x] Promote / transfer endpoints — `/guilds/{id}/{promote,demote,transfer,kick}/{account_id}` already shipped
- [x] Application flow — `/guilds/{id}/apply` + `/guilds/applications/{id}/{accept,reject}` already shipped
- [x] Invite flow — `GuildInvite` model + 6 endpoints (invite/accept/reject/cancel/list outgoing/list mine), 10 lifecycle tests. See "Guild invite flow (2026-04-25)" below.
- [x] Soft-delete for direct messages — sender-only `DELETE /dm/{id}`, body redacted to `[deleted]` in /dm/with/* + /dm/threads, row stays so reports/audit resolve. Migration `177a30b78d4a`.
- [ ] Per-guild achievements / milestones

### Raids
- [x] Scheduled raid auto-start (`_auto_rotate_raids` in worker)
- [x] Per-attempt cooldown (`RAID_ATTEMPT_COOLDOWN_SECONDS`, 10 min)
- [x] Leaderboard endpoint (`GET /raids/leaderboard`)
- [x] Boss-only unique specials (`BOSS_PHASE` type — see Combat depth log)

### LiveOps
- [x] Scheduled future events — admin POST /admin/liveops accepts `starts_at` (defaults to now), bounded ±5min/+90d
- [x] Preview endpoint for upcoming / not-yet-started events — `GET /liveops/scheduled?horizon_days=N`
- [x] Seed event for `BONUS_GEAR_DROPS` kind — `events/2026-07-04_summer_slowdown.json` ships one

### Content
- [ ] See Sprint D

### Combat
- [x] More status effects (FREEZE / BURN / HEAL_BLOCK / REFLECT) — see "Combat depth (2026-04-25)" below
- [x] Faction affinity / synergy bonuses — 3/4/5-of-faction tiers, baked into base_atk/base_def before sim
- [x] AoE revive — new `AOE_REVIVE` special type, respects HEAL_BLOCK on corpses
- [x] Combat log pruning — `trim_combat_log()` already in place at 200-entry cap

### Infrastructure
- [ ] Postgres end-to-end smoke (Sprint C)
- [ ] Docker image build + push to a registry (Dockerfile exists, never built)
- [x] Automated daily DB backup — `scripts/backup_db.sh` (see Sprint C above)
- [x] Graceful shutdown — worker cancels + in-flight battles finish (lifespan handles it; documented in RUNBOOK with uvicorn flag recommendations)
- [ ] Deploy target picked (Fly / Railway / Render / plain VM)

### Observability
- [ ] OpenTelemetry tracing (propagate request IDs into spans)
- [x] Alerting thresholds documented (5xx rate, p99 latency, worker, 429s, purchases, webhooks, token revocations, throughput drops) with PromQL — `docs/RUNBOOK.md`
- [ ] Dashboard screenshots in `RUNBOOK.md` — layout drafted; capture once prod has real traffic

### Anti-cheat / validation
- [x] Per-account rate limit on `/battles` (Sprint A)
- [x] Cap arena attack attempts per hour — `arena_attack_per_minute_per_account`
- [x] Audit all endpoints for `hero_instance_id` ownership check — e2d2ff5, 7 guard tests
- [x] Per-IP guild-message rate limit — e2d2ff5 (per-IP bucket, Redis-backed when configured)
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

**Anti-cheat audit + account-depth sprint (2026-04-25, e2d2ff5)**
- Cross-account ownership audit: 7 guard tests across hero/gear/battle/arena routes
- Active sessions: `GET /me/sessions`, single + bulk revoke; refresh tokens carry IP/UA/last_used_at (migration `3aa50c822bb6`)
- GDPR art. 20 export: `GET /me/export` — full account dump w/ secrets redacted + per-table caps
- Per-IP guild-chat rate limit layered alongside per-account bucket

**Big batch — battle visuals + UX polish + worker hygiene (2026-04-25 → 2026-04-26)**
Bunch of self-contained wins shipped together. By area:

Battle replay viewer (`app/static/battle-phaser.html`)
- Lunge-on-hit attack animation: attacker slides forward, damage visual
  fires on contact frame, slides back. Multi-hit specials (TBFAM 4-hit,
  AOE strikes, BOSS_PHASE) consolidate into one lunge-and-stay via
  cursor-lookahead.
- DamagePopup-style scale-pulse-fade damage numbers + crit variant +
  fan-out staggered x so 4 hits don't stack at the same point.
- BOSS_PHASE cinematic: red flash + camera shake + name banner.
- HAIL_MARY cinematic: gold flash + role-flavored banner.
- FACTION_SYNERGY top banner per side.
- REFLECT bounce-beam from defender to attacker.
- Status-aware frame tints (FREEZE cyan, BURN orange, HEAL_BLOCK
  magenta, etc.) so dominant status reads at a glance.
- Color-coded emoji glyphs on the status row.
- Per-stage backgrounds — `stage_code` exposed on `BattleOut`,
  cluster-of-fuckery SVGs copied into `app/static/backgrounds/cof/`,
  thematic mapping per stage code with cubicle as default.
- Keyboard shortcuts: Space/K play-pause, N/→ step, R restart, 1-5
  speed presets, ?/H toggle in-canvas help overlay, Esc closes.
- 6 previously-missing event handlers wired (FROZEN, STATUS_BROKEN,
  HEAL_BLOCKED, REVIVE_BLOCKED, REFLECT, FACTION_SYNERGY).

Combat depth (`app/combat.py`)
- 4 new statuses: FREEZE / BURN / HEAL_BLOCK / REFLECT.
- Faction synergy: 3/4/5-of-faction tiers grant ATK/DEF baked into
  base before sim, logged once for the replay.
- AOE_REVIVE special type — respects HEAL_BLOCK on corpses.
- AOE_HEAL primitive (Mother's Day Applecrumb's signature).
- BOSS_PHASE special type — 3 raid bosses retuned to use it.
- Hail-mary at ≤5% HP — one-shot per battle, role-flavored
  (ATK 'Last Stand' / DEF 'Hold The Line' / SUP 'You're Welcome').

Sprint D close — raid depth (`app/worker.py`, `app/routers/raids.py`)
- Auto-rotate, per-attempt cooldown, leaderboard endpoint were
  already shipped (TODO drift swept).
- BOSS_PHASE special type rounded out the last item.

Mother's Day 2026 event (`events/2026-05-10_mothers_day.json`)
- Applecrumb (MYTH SUP) seed + 48h DOUBLE_REWARDS + Bouquet bundle.
- Activate via `uv run python -m scripts.activate_event` on launch day.

Hero card art (66 files via the cluster-of-fuckery pipeline)
- 33 trading-card portraits in `app/static/heroes/cards/`
- 33 auto-cropped busts in `app/static/heroes/busts/` — crop
  recipe (top=9.0%, side=88.1%, h-centered, 512×512) reverse-
  engineered from the 5 reference busts.

Authn / security (`app/routers/auth.py`, `app/routers/me.py`,
`app/observability.py`, migrations)
- Post-review hardening: Redis-backed rate buckets, X-Forwarded-For
  trust gate, `/me/export` rate-limited, `SessionOut.is_current`
  computed from last_used_at.
- Refresh-token fingerprint anomaly detection — sha256(UA|IP) at
  issue, compared on rotation, mismatch logs warning + ticks
  `refresh_token_anomaly_total` Prometheus counter.
- `POST /me/password` for authed password change.

UX polish
- Toast notifications (`app/static/toast.js`) — replaces 9 alert()
  callsites with bottom-center stack, color-coded by kind.
- Skeleton placeholders (`.skeleton`/`.skeleton-line`/`.skeleton-grid`
  in shell.html) for the initial #content swap + reused across
  partials.
- Shared `.empty-state` component (icon + headline + actionable hint)
  applied to arena / daily / mailbox / roster / friends / conversations
  / purchases / event / shop empty paths.
- Account / security panel (new ⚙️ Account tab) — sessions list with
  per-row revoke + bulk revoke, GDPR data export, 2FA inline setup
  (secret + otpauth deep-link, recovery codes display) + disable form,
  password change form.
- Raids panel (new 🐉 Raid tab) — surfaces /raids/mine + /raids/leaderboard
  with empty states for not-in-guild and no-active-raid.
- Friends partial: DM delete link on own bubbles, deleted bubbles
  italic+0.55 opacity.
- Bell badge: visibility-aware polling (paused while tab hidden,
  immediate refresh on focus / visibilitychange / window focus).

Worker hygiene (`app/worker.py`)
- Battle log compaction — battles older than 30 days get log_json
  replaced with a single COMPACTED marker (~30KB → ~80 bytes each).
  Idempotent + capped at 500 rows/tick.
- Refresh-token cleanup — revoked or expired rows older than 30 days
  hard-deleted; replaced_by_id is ondelete=SET NULL so live tokens
  in a rotation chain aren't cascaded.

DM soft-delete (`app/routers/friends.py`, migration `177a30b78d4a`)
- Sender-only `DELETE /dm/{id}`, body redacted to `[deleted]`
  in /dm/with/* + /dm/threads. Row stays for audit/abuse-report.

Tests
- 49 new tests added across the session (combat statuses + faction
  synergy + AOE_REVIVE + AOE_HEAL + BOSS_PHASE + hail-mary + sessions
  is_current + GDPR sessions/admin_actions blocks + DM soft-delete +
  worker compaction/cleanup + change-password + account partial +
  raids partial + guild invites + refresh-token fingerprint).
- 3 pre-existing flaky tests fixed (guild-tag collision widened,
  RNG-dropped material rate iterations bumped, achievement-count
  unlock-set check).
- Suite at 473 passed clean post-session (was 411 at start).

Docs
- `docs/BATTLE_VISUALS_STACK.md` — three full stack picks (free
  cluster-of-fuckery / DragonBones / Spine Pro) with tradeoff matrix
  and recommended starter (Plan A).
- `docs/RUNBOOK.md` — alerting fleshed out (10 alerts with thresholds
  + severity tags + PromQL), 11-row PromQL cookbook, 7-row Grafana
  dashboard layout, graceful shutdown uvicorn flag recommendations,
  refresh-token anomaly counter alert.
- `events/README.md` — Mother's Day calendar entry.
- `app/static/heroes/cards/` notes (in memory): 3 unmatched filenames
  intentional (`The_Man_The_Dev`, `applecrumb`, `ticket_gremlinx4`).

**Guild invite flow (2026-04-25)**
The inverse of /guilds/.../apply: leader/officer asks a specific player; the
player decides. Lifecycle and statuses match GuildApplication — same
PENDING/ACCEPTED/REJECTED/WITHDRAWN states.
- New `GuildInvite` model (`app/models.py`) + alembic migration
  `50b27201679e_add_guild_invites`. Fields: account_id (target), guild_id,
  inviter_id (NULL on inviter delete), status, message, created_at, decided_at.
- Six endpoints in `app/routers/guilds.py`:
  - `POST /guilds/{id}/invite/{account_id}` — officer-only, validates target
    isn't banned / already in a guild / already pending invited
  - `GET  /guilds/{id}/invites?include_decided=` — officer view
  - `GET  /guilds/invites/mine` — invitee view
  - `POST /guilds/invites/{id}/accept` — joins, auto-rejects all other
    pending invites for the player
  - `POST /guilds/invites/{id}/reject`
  - `DELETE /guilds/invites/{id}` — officer cancels (WITHDRAWN)
- 10 new tests in `tests/test_guild_invites.py` covering pending→accepted,
  reject, officer cancel, member-cannot-invite, duplicate guard, can't
  invite a player already in a guild, first-accept-wins auto-reject of
  competing invites, outgoing-list authz, accept-wrong-recipient 404,
  banned-target 409.

**Sprint D close — Raid depth (2026-04-25)**
Three of four items in Sprint D were already in the codebase (`_auto_rotate_raids`,
the `RAID_ATTEMPT_COOLDOWN_SECONDS` gate in `attack_raid`, and the public
`GET /raids/leaderboard` endpoint) — TODO had drifted from reality. Marked
those done. The remaining item: boss-only unique specials.
- New `BOSS_PHASE` special type in `app/combat.py` — single-cast multi-effect
  AOE: damage + N statuses on every live enemy + N self-buffs on the boss.
  Statuses are scaled by special_level the same way other specials are.
- Three raid bosses re-tuned in `app/seed.py`:
  - Legacy Colossus → Bureaucratic Inertia: AOE + DEF_DOWN + HEAL_BLOCK,
    self-stacks REFLECT each cast (focus-fire becomes a trap).
  - C-Suite Hydra → Mandatory Re-Org: AOE + FREEZE on all (any damage
    breaks it, so priority puzzle), self-buffs ATK_UP.
  - Chaos Dragon → Cascading Outage: AOE + BURN on all (stat-independent
    bleed), self ATK_UP.
- 2 new unit tests in `tests/test_combat_unit.py` covering BOSS_PHASE shape
  and the corpse-status edge case.

**Combat depth (2026-04-25)**
Pure-resolver expansion in `app/combat.py` — no DB or schema changes:
- 4 new statuses on `StatusEffectKind`: FREEZE (skip-turn, breaks on damage),
  BURN (max-HP-fraction DoT alongside POISON), HEAL_BLOCK (suppresses heal /
  lifesteal / revive), REFLECT (returns N% damage to attacker, no recursion).
- Faction synergy: 3/4/5 same-faction units on a team grant tiered ATK + DEF
  bonuses, baked into base_atk/base_def before sim and logged once for the
  replay viewer. Mixed teams stay vanilla.
- New `AOE_REVIVE` special type — resurrects every dead ally at frac HP;
  HEAL_BLOCK on a corpse blocks the rez (counter-comp lever).
- All damage paths now thread `attacker`/`log` through `_apply_damage` so
  REFLECT can bounce. `_heal()` and `_revive()` helpers centralise heal-
  routing through HEAL_BLOCK and free callers from inline HP arithmetic.
- 10 new unit tests in `tests/test_combat_unit.py` covering each status,
  AOE_REVIVE, HEAL_BLOCK-blocks-rez, and synergy tier ladder.
- `CLEANSE` extended to strip BURN, FREEZE, HEAL_BLOCK alongside the old
  POISON/DEF_DOWN/STUN set.

**Post-review hardening (2026-04-25)**
Code-review pass against e2d2ff5; landed fixes:
- [x] Per-action rate buckets routed through `_make_bucket()` factory — Redis-backed when `rate_limit_backend=redis` (was: in-memory only, broke under horizontal scale)
- [x] `trust_forwarded_for` config flag gates `X-Forwarded-For` parsing in middleware + auth IP capture (was: trusted unconditionally, spoofable without proxy)
- [x] `/me/export` rate-limited (1/min per account) via `enforce_data_export_rate_limit` — factory + route both wired
- [x] `SessionOut.is_current` from most-recent activity (`last_used_at` falling back to `issued_at`); single live session always flagged, ties broken by id
- [x] `data_export.py`: dropped dead `_try_json(None) or` expr; `_iso_now` hoisted to module-top; new `sessions` block (live refresh tokens, hash redacted) + `admin_actions_against_me` block (audit-log entries where this account is the target)
- [x] `tests/test_cross_account_ownership.py`: silent `return` → `pytest.skip()` so RNG-gated skips are visible in suite output

**Sprint H (PWA) + art pipeline (2026-04-24)**
- PWA manifest + service worker + keyboard-sword app icons — installable on Android / iOS
- 5 pilot hero trading cards (ChatGPT-generated): ticket_gremlin, jaded_intern, the_sysadmin, the_consultant, the_founder
- Dual-layer art pipeline: `app/static/heroes/cards/*.png` (full trading cards) + `app/static/heroes/busts/*.png` (auto-cropped grid thumbnails)
- MYTH rarity tier added + TBFAM seeded as pilot MYTH hero
- Hero art prompt pack at `docs/hero_art_prompts.md` — 31 more characters queued

**Phase 1 shipped (2026-04-24)** — see `docs/PRD.md § 6` for full scope + acceptance test
- 1.1 Guided first-session flow: Next-Step CTA card on /me, tutorial auto-battle, +1 free summon credit reward, 3-COMMON starter team on register
- 1.2 Roster redesign: rarity-tabbed grid + bottom-sheet detail overlay with real bust/card art, duplicate collapse, placeholder fallback
- 1.3 Team presets: POST/GET/DELETE /me/team-presets (5 per account) + GET /me/last-team + preset dropdown on stages + "save team" button on battle win
- 1.4 Dedicated Summon tab: banner header, pity progress bar, recent-pulls feed, x1/x10 buttons
- 1.5 Jump-Ahead starter pack SKU ($4.99, 7-day window, RARE hero grant)
- 1.6 Signed-in pill badge, dead-code cleanup
- Acceptance test `tests/test_phase1_acceptance.py` — 9-step end-to-end flow, 275/275 tests green

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
