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
- Analytics: PostHog self-hosted, 12 events instrumented, funnels
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

### F. Roster / summon UX overhaul (from play-testing)
Medium-sized but the highest-leverage UX work right now. See Product Direction section above for full context.
- [ ] Group duplicate heroes in the roster view (same template → single card with count)
- [ ] Rarity-separated tabs in roster (Common / Uncommon / Rare / Epic / Legendary / Myth)
- [ ] Pretty x10 summon result (grid of cards w/ rarity borders) — *partially landed 2026-04-24*
- [ ] Per-hero detail page: stats, skill level, gear loadout, next-star preview
- [ ] Saved team presets (Arena / Campaign / Raid) — QoL, paid unlock candidate
- [ ] "Use last team" one-click on the Battle tab

### H. PWA — put it on a phone home screen
Cheapest path to "on my phone, feels like an app." See [Mobile Strategy](#-mobile-strategy) below for the full roadmap (PWA → Capacitor → native).
- [ ] `app/static/manifest.webmanifest` — name, short_name, icons (192/512 + maskable), theme_color, background_color, display=standalone
- [ ] Service worker at `/app/sw.js` — offline shell for `/app/` shell + cached static assets, network-first for `/me` and other live endpoints
- [ ] Apple touch icons + meta tags in `templates/base.html` (Apple ignores standard manifest icons, needs its own)
- [ ] Test: install on Android Chrome, install on iOS Safari, confirm icon + splash + offline-launch both work
- [ ] Register service worker from the dashboard entry template

### G. Combat depth (from play-testing)
Design-first sprint — probably 2-3 iterations before it's good. Reference games listed in Product Direction.
- [ ] Melee / ranged attack split (extend `basic_mult` model → `melee_mult` + `ranged_mult`)
- [ ] Mana or spell-point resource for ranged/magic heroes
- [ ] Hail-mary ability at ≤5% HP (role/faction-flavored one-shot)
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
- [ ] **Loading skeleton designs** — shimmer states per section (me / roster / battle setup).
- [ ] **Empty-state illustrations** — "no opponents in arena", "no guild yet", "no active raid", "no heroes yet — do a pull."
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
