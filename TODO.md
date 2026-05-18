# hero-proto — TODO & Test Reference

Living list. Tick items `[x]` as done. Add new ones at the bottom of the relevant section.

Last updated: 2026-05-12 PM (Shard remap Phases 1+2+3 shipped: dupe HeroInstances collapsed to template-shard balances; gacha dupes now credit shards instead of creating rows; skill_up converted to shards (5/15/40/100 per tier 1→5); fodder `/ascend` endpoint deleted. Quaternius rig migration — per-archetype embedded combat clips, KayKit shared-rig file dropped. Per-turn countdown timer (server-authoritative 120s) for interactive combat. Battle 3D: overhead HP bars + team B repositioned. Battle setup: rarity-grouped roster + duplicate stacking.)

---

## 📊 Where we're at

- **Phases shipped:** Phase 1 ✅, Phase 2 (2.1–2.6) ✅, Phase 2 review fixes ✅, Phase 2 polish + Phase 3.1/3.2 starters ✅, Phase 3.5 Alignment Fork ✅, Phase 4 (mobile/wrap/store/push) ✅. Onboarding quests + arena tickets/drip/weekly payout + countdown timers shipped 2026-05-06. CraftPix sprite system shipped 2026-05-07 — 26 rigs (24 CraftPix + Gary stick-figure + Dark Assassin), each hero template_code mapped to a rig, bust portraits in unit cards, all stages have backgrounds.
- **Backend:** Combat resolver w/ 8 statuses + faction synergy + hail-mary + BOSS_PHASE + variance + attack-channel split. Refresh-token rotation w/ reuse + fingerprint anomaly detection. Stripe + Apple StoreKit + Google Play Billing adapters. Per-day rate limits on friends/DMs. Alignment fork: `POST /story/alignment`, faction-gated chapters, exclusive hero grants, arena same-alignment soft matchmaking.
- **Frontend:** React SPA at `/app` (built with Vite, served from `app/static/spa/`). All routes wired. Auth guard redirects unauthenticated users to login. Login page: Sign In / Register / Forgot-password tabs. NavBar hides auth-required tabs when logged out; shows Sign-out button when logged in. 401 interceptor auto-clears JWT. Dashboard redesigned (two-column grid, profile banner, stat cells, hero mini-roster). Story route overhauled (expandable chapters, stage-level cutscene previews, alignment fork choice UI). Faction badge in profile banner. Original vanilla-JS shell still present at `/app/partials/*` but SPA is the primary client.
- **Observability:** Prometheus `/metrics`, JSON logs, request IDs, Sentry (DSN-gated), worker supervisor + 9 alerts in RUNBOOK + 11-row PromQL cookbook + 7-row Grafana layout.
- **Infra:** Redis-backed rate limiter (horizontal-scale ready). CI matrix on SQLite + Postgres per push.
- **Tests:** **806 passed / 2 skipped** (backend, +5 from shard skill_up coverage) + **84 passed / 1 pre-existing dioramaLoader flake** (frontend vitest). `pytest` green (one unrelated rest_xp timing flake); `vitest` green except for unrelated Three.js Box3 mock. Acceptance scripts:
  - `scripts/startup_check.py` — admin/operator health check
  - `scripts/client_walkthrough.py` — 17-section feature tour (was 13; +4 Phase 2 surfaces)
  - `tests/test_phase1_acceptance.py`, `tests/test_phase2_acceptance.py` — bright-line e2e
- **Mobile:** Capacitor scaffold in `mobile/` — `package.json` + `capacitor.config.ts` targeting `app/static/spa`. `POST/DELETE /notifications/device-token` endpoints live. `app/push.py` FCM stub (no-op without `FCM_SERVER_KEY`). `frontend/src/api/push.ts` — call `initPush()` after login. iOS builds go through Codemagic / GitHub mac runners.
- **Docs:** `README.md`, `docs/RUNBOOK.md`, `docs/PRD.md`, `docs/PHASE_2_HUMAN_TEST.md`, `docs/PLAN_B_INTEGRATION.md`, `docs/BATTLE_RIG_EVENT_MAPPING.md`, `docs/BATTLE_VISUALS_STACK.md` all current.
- **Art:** 33 trading-card portraits + 33 auto-cropped busts in `/app/static/heroes/`. Cluster-of-fuckery stick-figure animation pipeline available outside repo. DragonBones Mecha 1004B sample lives in repo as Plan B feasibility demo.

### Shipped 2026-05-12

**Shard remap — Phases 1+2+3** (commits `1cc56ef`, `ae5384a`; production live):
- **Phase 1** — Alembic migration `f9fcd159c6dd` collapses duplicate `HeroInstance` rows per `(account_id, template_id)` to a single canonical row + per-template `template_shards_json` balance. Variance-aware tie-breaking picks the highest-stat dupe as canonical; the rest are deleted and credited as shards at their rarity rate. Gear with FK to deleted heroes auto-detaches via `ondelete=SET NULL`. Locally collapsed 1 duplicate + credited shards to 1 account; auto-runs on Fly via `alembic upgrade head` in `app/main.py`.
- **Phase 2** — Gacha pulls (standard, event-banner, friend-points) now skip `HeroInstance` creation on dupes and grant shards instead. `SummonOut` schema extended with `is_duplicate` + `shards_granted` fields.
- **Phase 3** — `skill_up` rewritten to spend template shards (5/15/40/100 per tier 1→5) via `app/template_shards.py::spend()`. The fodder-based `/heroes/{id}/ascend` endpoint deleted entirely (only `/ascend-with-shards` remains, established 2026-05-08). `AscendIn` + `SkillUpIn` schemas removed. `upgrade_preview` gates `special_up.available` on shard balance.
- **Frontend**: HeroDetail's dead "⭐ Star Up (fodder)" button removed. Skill Up button shows `(have/cost shards)`, disables on insufficient balance, invalidates `template-shards` query on success.
- **Tests**: +5 in `test_template_shards.py` (skill_up succeeds / 409 insufficient / 409 max-level + Phase 2 contract); `test_cross_account_ownership.py` updated; `test_phase2_acceptance.py` rewritten to validate shard credit instead of dupe-variance. Smokes `smoke_ascend.py` + `smoke_skill.py` rewritten against shard API. **806 passed, 1 pre-existing rest_xp flake unrelated.**

**Quaternius rig migration**:
- Migrated all 6 KayKit archetypes (knight/barbarian/mage/ranger/rogue/rogue_hooded) to Quaternius RPG Characters chibi pack. Each archetype now ships embedded per-class combat clips: `Sword_Attack` (knight/barbarian), `Staff_Attack` (mage), `Dagger_Attack` (rogue/rogue_hooded), `Bow_Shoot` (ranger). KayKit shared `kaykit_general.glb` + procedural arm-swing fallback (`proceduralClips.ts`) both removed.
- Engineer/Monk rig staged at `frontend/public/battle-3d/heroes/monk.glb` with full clipset registered in `clipMap.ts`. Pure config wiring left to do when a template needs it.

**Per-turn countdown timer for interactive combat**:
- `InteractiveStateOut` extended with `turn_started_at` + `turn_timeout_s` (default 120s). Server-authoritative; lazy timeout enforcement on next poll. Client renders countdown; on expiry, server forfeits the actor's turn. Same flow wired into raid interactive attacks.

**Battle 3D layout polish**:
- Overhead world-space HP bars per unit (replaces HUD bars only).
- Team B portrait stack moved to lower-right corner so it doesn't overlap the 3D render.

**Battle Setup roster QoL**:
- Roster groups by rarity (LEGENDARY → COMMON tiers visible at a glance).
- Vanilla duplicates stack into a single chip with count + variance hint instead of N near-identical buttons.

### Shipped 2026-05-10

**Battle 3D Viewer v1** (interactive mode only — instant-replay still uses `battle-arena.html`):
- Replaces empty "BATTLE" watermark in `BattlePlayRoute` with a Three.js scene rendering KayKit chibi heroes on programmatically-composited dioramas. Animation-driven from interactive combat events (DAMAGE/DEATH/SPECIAL).
- **Backend** (`fa278fe`, `7b020e0`): `InteractiveStateOut` extended with `stage_code` + `last_event` (persistence-across-empty-polls). `last_event` captured at `_state_out` from `log_delta[-1]`; preserved between polls so the animation driver isn't starved. `stage_code` set at `create_stage_session(...)` constructor call. Raid sessions intentionally null (no per-stage code; falls back to default theme).
- **Frontend** (`docs/superpowers/specs/2026-05-10-battle-3d-interactive-viewer-design.md` + `-pre-plan-addendum.md`): new `frontend/src/battle3d/` module — `Battle3DScene.tsx`, `Battle3DErrorBoundary.tsx`, `heroLoader.ts`, `dioramaLoader.ts`, `animationDriver.ts`, `clipMap.ts`, `archetypeMap.ts` (auto-generated from `app/rig_map.py` via `scripts/gen-archetype-map.py`), `constants.ts`, `telemetry.ts`. Lazy-loaded chunk (~624KB / 162KB gz) isolated from main bundle via `React.lazy + Suspense`. Error boundary falls back to watermark on Three.js crash.
- **Assets** (~6 MB Draco-compressed, well under 20 MB spec budget): 7 chibi archetypes — 6 KayKit (knight/barbarian/mage/ranger/rogue/rogue_hooded) sharing rig clips from `kaykit_general.glb` + Quaternius Cleric as druid (embedded clips). 2 dioramas (server-closet, data-center) composited from SciFi MegaKit primitives via `frontend/scripts/compose-dioramas.mjs` using `@gltf-transform/core`.
- **Architecture insight**: KayKit hero meshes ship with **zero embedded animations** — clips live in shared rig files. `heroLoader` returns `{ scene, animations, archetype }` where KayKit archetypes pull animations from the shared `kaykit_general.glb` (cached separately) while druid uses its own embedded clips. Three.js `AnimationMixer` retargets the shared clips onto each hero's skeleton automatically because they share track-name structure.
- **Tests**: 32 vitest tests in `frontend/src/battle3d/__tests__/` + 3 new pytest tests in `tests/test_battle_3d_state.py`. 0 regressions across battle suite.
- **Telemetry**: `recordBattle3DMetric("battle3d.first_frame_ms", ...)` and `battle3d.mount_ms` emitted via `console.info` (real analytics sink TBD — left as v1.1 follow-up with `// TODO` in `telemetry.ts`).
- **Bug caught by smoke test**: hero/diorama URLs hard-coded to `/battle-3d/...` (root-absolute) but SPA mounted at `/app/static/spa/`. Fixed via `import.meta.env.BASE_URL` (`d651984`).

**Rare Collections v1** (shipped earlier today):
- 12 collections (3 of each rarity tier) + 8-track piece reward system live in production. `Collection` table model + Account columns. Drops surface in battle victory overlay + dedicated `/collections` route + loot popup + nav tab.
- 8-track grants from 3 sources: weekly chest, Tower of Trials floor 50, raid top 10%.
- Smoke-tested in production (`hero-proto.fly.dev`) 2026-05-10 morning.

### Shipped 2026-05-07 / 2026-05-08

**Onboarding quest system** (`onboarding_week_one`):
- New `Quest` + `AccountQuest` models + migration `db7eac125e36`. Compound idempotency (`uq_account_quests_account_quest`).
- Fire-and-forget `app/quest_service.py::record_event()` — never raises; threads through `BATTLE_COMPLETE`, `BATTLE_WIN`, `STAGE_CLEARED`, `HARD_STAGE_CLEARED`, `LEGENDARY_STAGE_CLEARED`, `ACCOUNT_LEVEL_REACHED` (threshold-based, not counter), `STORY_CHAPTER_CLEARED`, `STORY_ARC_CLEARED`, `HERO_LEVELED` (fires on level==5 exactly), `SUMMON_COMPLETE` (x1 + x10 + event_banner), `GEAR_EQUIPPED`, `ARENA_WIN`, `GUILD_JOINED`, `RAID_CONTRIBUTED`, `DAILY_QUEST_COMPLETE` (day-set tracking), `FACTION_CHOSEN`.
- 19-task quest, 7-day window, claim choice between EPIC hero or 500 gems + always-granted "Survived Onboarding" cosmetic frame. `pulls_since_epic` resets on Epic claim.
- `app/quests.py::auto_enroll(db, account)` — idempotent, FK-guarded; called from auth register flow.
- Endpoints: `GET /quests/active`, `POST /quests/{id}/claim` (with `SELECT FOR UPDATE` lock + 503 if no Epic pool), `POST /quests/{id}/dismiss` (dismissed quests still progress).
- Frontend: floating bottom-right `QuestWidget`, expandable, gold pulse on completion, `ClaimModal` for choice. CoachMark component for first-screen tooltips on 7 routes.
- Existing accounts (e.g. ridler69) backfilled via `fly ssh console` script.

**Arena economy + countdowns** (spec: `docs/superpowers/specs/2026-05-06-arena-tickets-and-countdowns-design.md`):
- Account fields: `arena_tickets_stored`, `arena_tickets_last_tick_at`, `arena_weekly_wins`, `arena_weekly_key`. Migration `a4e1c5d2b8f9` (cross-DB safe — nullable DateTime + UPDATE backfill, not raw `CURRENT_TIMESTAMP` server_default).
- New `arena_weekly_payouts` table with `(week_key, account_id)` PK as idempotency lock + `acknowledged_at` for modal dismissal.
- `app/economy.py`: `compute_arena_tickets`, `consume_arena_ticket`, `seconds_until_next_energy`, `seconds_until_next_ticket` — mirror the existing energy regen pattern. 4h regen, 5-ticket cap.
- `app/arena_payout.py`: ISO week-key helpers + `distribute_pending(db)` lazy distributor (idempotent via PK), `reset_weekly_counter_if_stale`. Top-50 by rating, `arena_weekly_wins >= 1` eligibility filter.
- `app/arena_constants.py`: per-attack drip (win 75c/3s/5g, loss/draw 25c/0/0, ±20% coin jitter), weekly bracket payouts (1: 500g + frame, 2-5: 250g, 6-20: 100g, 21-50: 50g), `arena_champion` cosmetic frame.
- `/arena/attack` gates on `consume_arena_ticket` (429 with `Retry-After` if 0), drips rewards, increments `arena_weekly_wins` on win.
- `/arena/weekly/acknowledge` clears `acknowledged_at` for modal flow. `/me` calls `reset_weekly_counter_if_stale` + `distribute_pending` on every hit; returns `energy_next_tick_in`, `arena_tickets`, `arena_tickets_cap`, `arena_tickets_next_tick_in`, `arena_weekly_wins`, `pending_arena_rewards`.
- Frontend: `useCountdown` + `useDailyResetCountdown` hooks (Rules-of-Hooks-safe — fix shipped after a regression). Inline `+1 in M:SS` in `CurrencyBar`. `Arena/TicketHeader` with full-cap timer. `Me/RecurringResources` panel. Attack result toast shows drip rewards. `PendingArenaReward` modal for weekly payouts (auto-shows when `pending_arena_rewards` non-empty).

**CraftPix battle rigs + bust portraits in prod arena**:
- 24 character packs sliced from CraftPix free packs (knights x3, werewolves x3, wizards x3, gorgons x3, yokai x3, ninjas x3, minotaurs x3, satyrs x3) — frame-strip slicer at `scripts/slice_craftpix_packs.py`. Plus `scripts/slice_existing_packs.py` for pre-existing orc/soldier sheets.
- Slicer auto-detects frame size from sheet height (handles 96/100/128px frames). 5 animation slots per character: idle/attack/hurt/die/run. 2,800+ individual PNG frames committed.
- `app/static/battle-arena.html` ported from single-rig stick-figure to 26-rig system: `RIGS` catalog, `TEMPLATE_TO_RIG` map (35 hero templates → CraftPix rigs), `rigForTemplate(template_code)` resolver, per-unit rig stored on `spriteState`. Sprite size bumped from 80×140 to 250×250; slot positions widened.
- Bust portraits already supported via `bustUrl` from `template_code`; only fix needed was preserving `template_code` on the unit object so `rigForTemplate` could resolve it.
- `STAGE_CODE_TO_BG` extended to all 16 normal stages + 13 story arcs + 3 raid bosses. Difficulty prefix strip (`H-`, `N-`) so all difficulty tiers share their base stage's bg.
- Hooks bug fix: `useCountdown` calls hoisted above early returns in `CurrencyBar` (was causing minified React error #310 on Summon page).
- Verified end-to-end on prod with fresh test account: First Ticket (Normal + Hard), Legacy Server Room — rigs render, busts show in turn-order strip + active panel, mapped backgrounds load.
- Demos: `/app/static/battle-arena-knights.html` (random 6-rig roster + reroll, supports `?seed=foo` and `?og=1` to pin Gary + Dark Assassin), `/app/static/character-roster.html` (24-character catalog with per-animation toggle).

**Operational**:
- Anthropic API key rotated (Fly secret hash changed; smoke-tested via SSH calling `claude-haiku-4-5` from prod env).

### Verified green today (2026-04-29)

- Suite: 630 passed, 2 skipped.
- Build revision system shipped (2026-04-30):
  - `app/version.py` resolves `{version, branch, built_at}` once at import time. Order: `HEROPROTO_BUILD_VERSION` env → `git rev-parse --short HEAD` → `"dev"`. Same fallback for branch and time.
  - `GET /version` endpoint surfaces the resolved info — public, safe to expose.
  - `Dockerfile` accepts `--build-arg HEROPROTO_BUILD_VERSION` / `_BUILD_TIME` / `_BUILD_BRANCH`, bakes them as runtime env so the running image reports its own identity.
  - `frontend/vite.config.ts` resolves a SPA build version (env override → git short SHA → "dev") and bakes it as `__APP_VERSION__` + `__APP_BUILD_TIME__` constants. `@types/node` added as devDep so config compiles cleanly.
  - `frontend/src/components/VersionTag.tsx` — floating bottom-right badge on every screen. Click expands to show SPA version, SPA build time, plus calls `/version` on the API and shows the backend version too. **Goes red when SPA and API versions disagree** — instant "is this the new build?" check.
  - `mobile/build-prod-android.sh` rewritten with a loud version banner: prints version + branch + built-at + API target before/after build, and bakes the same values into the SPA via `VITE_APP_VERSION` / `VITE_APP_BUILD_TIME`. Banner end-card tells you to look for the badge in the corner of the running app.
  - Closes the "is the emulator running my latest build?" guessing game permanently.

- FCM (Android push) live-fired (2026-04-30):
  - `fly secrets set FCM_PROJECT_ID="hero-proto"` + `FCM_SERVICE_ACCOUNT_JSON` → `fly deploy`
  - `GET /admin/push/status` returns `{"fcm":true,"fcm_project_id":"hero-proto",...}` from prod
  - `POST /admin/push/test` accepts and routes; verified config-side, end-to-end emulator delivery still pending the prod-build install on the emulator.
  - APNs intentionally unset (iOS on hold).

- Logout redirect (2026-04-30):
  - Sign out from NavBar or Me page → `window.location.href = '/'` (marketing landing) instead of `/app/login`. Hard exit out of the SPA so the user lands on the public site, not the SPA login screen that bounces them straight back into the 2FA flow.

- Sprint H ops cheatsheet (2026-04-30):
  - `CHEATSHEET.md` — 467-line ops/admin reference. Live URLs, Fly server lifecycle (deploy/restart/logs/secrets/DB), local dev, mobile build, testing, full admin endpoint table with curl recipes, env var reference, incident playbook, migration cookbook, game-specific SQL cheats, doc map, external service links. Pinned at the project root for ridler69's convenience down the road.

- Frontend gear UI surface (2026-04-29):
  - `frontend/src/api/gear.ts` — typed client (`GearOut`, `ARMOR_SLOTS`, `SLOT_META`, `SET_META`, `RARITY_COLOR`, `VETERAN_IT_SET`, `CHAPTER_NAMED_GEAR`) + `fetchGear`/`equipGear`/`unequipGear`.
  - `/app/inventory` — new route. Filterable gear browser (All / Named / Armor / per-slot), sorted named-first then rarity then power proxy. Named pieces get gradient borders, ✨ badge, italic flavor quote with rarity-colored leftbar.
  - `HeroDetail` — 9-slot equipment grid (3×3) with rarity-bordered tiles. Empty slot → opens picker modal showing all available pieces of that slot, sorted named-first. Filled slot → unequips. Named pieces get ✨ corner badge.
  - `Me` page — `VeteranSetCard`: 6-tile silhouette grid that fills in as pieces are earned (grayscale + 35% opacity when missing). Progress bar + count, gold-tinted gradient when complete. Hover tooltips show piece name + acquisition source.
  - `Story` chapter cards — locked/unlocked named-piece teaser with icon + name + "Legendary <slot> piece · clear chapter to unlock".
  - NavBar — `📦 Inventory` tab in the Heroes group.

- Phase 4 polish — armor system + story rewards (2026-04-29):
  - **Gear slots reshaped to head-to-toe armor** — `GearSlot` enum now has WEAPON + 6 armor slots (HEAD, CHEST, HANDS, WRIST, LEGS, FEET) + RING + AMULET. Old HELMET/ARMOR/BOOTS renamed to HEAD/CHEST/FEET; new HANDS/WRIST/LEGS added. Migration `b2c3d4e5f6a7` rewrites existing gear rows + scans `mailbox_overflow_json` for any embedded slot strings.
  - **Named gear infrastructure** — `Gear.name` + `Gear.flavor` columns added. `app/named_gear.py` is the canonical catalog with `grant_named_gear(db, account, code)` for idempotent grants. `GET /gear/mine` now surfaces both fields.
  - **The Veteran IT armor set** (6 LEGENDARY pieces, one per slot, fixed stats):
    - `help_desk_headset` (HEAD) — Chapter 1 reward
    - `power_suit_jacket` (CHEST) — Chapter 2 reward
    - `all_terrain_loafers` (FEET) — Chapter 3 reward
    - `cargo_pants_of_many_tabs` (LEGS) — granted at level-50 alignment fork (universal)
    - `burner_phone_wristband` (WRIST) — Chapter 4 RESISTANCE reward
    - `signing_gauntlets` (HANDS) — Chapter 4 CORP_GREED reward
  - Stats are upper-band Legendary (~RNG ceiling) but not best-in-slot — chasing top RNG rolls still matters.
  - Chapter outros (5 chapters) rewritten to namedrop the reward in-fiction. Bell notifications include the gear name + icon.
  - **Tests:** 8 in `tests/test_named_gear.py` covering catalog completeness, idempotency, chapter grants, alignment-fork LEGS grant, API surface, and old-enum-removal sanity.

- Phase 4.4 Prod mobile build flow (2026-04-29):
  - `frontend/src/api/client.ts` now reads `VITE_API_BASE_URL` at build time. Web/dev builds leave it unset (relative URLs); store-bound mobile builds bake in `https://hero-proto.fly.dev` (or wherever the live API lands).
  - `mobile/capacitor.config.prod.ts` — production Capacitor config without `server.url`, so the bundled SPA loads from `file://` and hits the absolute API.
  - `mobile/build-prod-android.sh` — one-shot helper: builds SPA with the right env, swaps configs, runs `cap sync`, restores dev config on exit. Result: open `mobile/android/` in Android Studio and Build > Generate Signed Bundle > .aab for Play Console.
  - Backend already deployed on Fly.io (admin-lockdown sprint). After merging this branch, run `fly deploy` to ship the new push code.

- Phase 4.3 Push delivery wired (2026-04-29):
  - **Migrated FCM legacy → FCM HTTP v1.** Legacy server-key API was sunsetted by Google in June 2024 and now returns 404 in production. New code mints OAuth2 access tokens from a Firebase service account JSON, caches them for 55 min, and POSTs to `https://fcm.googleapis.com/v1/projects/{project_id}/messages:send`. Stale-token detection now keys off `UNREGISTERED` / `NOT_FOUND` / `INVALID_ARGUMENT` instead of HTTP 410.
  - New env vars: `FCM_PROJECT_ID` + `FCM_SERVICE_ACCOUNT_JSON` (or `_PATH`). Old `FCM_SERVER_KEY` removed.
  - `app/push.py::push_provider_status()` reports config state per provider.
  - `GET /admin/push/status` — admin diagnostic, returns `{fcm: bool, apns: bool, ...}`.
  - `POST /admin/push/test` — fires a test push to the calling admin's own registered devices, echoes how many were dispatched. Wired into audit log.
  - APNs path unchanged (already on HTTP/2 + JWT, still current).
  - `fly.toml` documents the `fly secrets set` invocations for both providers.
  - 630 passed, 2 skipped — push token + admin endpoint tests still green.

- Phase 4.2 Store compliance shipped (2026-04-29):
  - In-app `/app/privacy` + `/app/terms` routes (`frontend/src/routes/Legal.tsx`) — concise summaries that satisfy Play Store / App Store "policy reachable from inside the app" requirement; bypass age gate + auth so unauthenticated users (and parents) can read them
  - Login page footer links to Terms + Privacy
  - Account page → Data &amp; Privacy section links to both policies
  - Age gate (`frontend/src/components/AgeGate.tsx`) — first-launch modal asks birth year, blocks <13, persists to `localStorage` under `age_gate_v1`. Wired into Shell. Birth year stays client-side (privacy policy explicitly notes this).
  - Account → Danger Zone delete button already calls `DELETE /me` (since e2d2ff5); confirmed surface meets Apple "in-app account deletion" requirement (effective 2024-06-30)
  - Play App Signing path documented (see Infrastructure / Android keystore hardening below)

- Phase 4.1 Capacitor wrap shipped (2026-04-29):
  - `DeviceToken` model + alembic migration `a1b2c3d4e5f6`
  - `POST /notifications/device-token` + `DELETE /notifications/device-token` (upsert, platform=fcm|apns)
  - `app/push.py` — FCM send stub; config-gated no-op when `FCM_SERVER_KEY` absent; stale 410 tokens pruned
  - `app/notifications.py` — `notify()` now fires `send_push_to_account()` (fire-and-forget, push failure never breaks in-app notification)
  - `mobile/` scaffold — `package.json` (@capacitor/core 6, push-notifications), `capacitor.config.ts` (webDir → `../app/static/spa`), `.gitignore`
  - `frontend/src/api/push.ts` — `initPush()` registers with FCM/APNs and POSTs token to backend; `unregisterPush()` on logout
  - 8 tests in `tests/test_push_tokens.py`
  - iOS builds: on Windows use Codemagic or GitHub Actions mac runners — do NOT use a macOS VM (Apple EULA)

- Phase 3.5 Alignment Fork shipped (2026-04-29):
  - `Account.faction` (EXILE → RESISTANCE / CORP_GREED) + `Account.alignment_chosen_at` + migration
  - Two new EPIC exclusive heroes: The Whistleblower (RESISTANCE SUP) + The Successor (CORP_GREED ATK) — not in summon pool; granted on chapter completion
  - 10 new story stages (5 per alignment path, orders 50–64)
  - Two alignment Chapters in story catalog with full cutscene content; gated by faction
  - `POST /story/alignment` — level-50 one-time fork; 403 < lvl 50, 409 if already aligned
  - Chapter-end hero grant via `_grant_alignment_hero()`; idempotent
  - Arena soft same-alignment matchmaking preference (RESISTANCE/CORP_GREED)
  - `/me` now returns `faction` + `alignment_chosen_at`
  - Story route: expandable chapter cards, per-stage cutscene previews, alignment fork choice card
  - Faction badge on dashboard profile banner (EXILE / RESISTANCE / CORP_GREED with colors)
  - 11 tests in `tests/test_alignment.py`
- Admin lockdown shipped (2026-04-28): superadmin tier, login brute-force lockout, admin rate limit (30/min), enumeration-safe register (always 200), email-verification gate on summon/shop (bypassed in test env), auto-send verification on register. Deployed to Fly.io, migration at head.
- SPA auth polish shipped (2026-04-28): Login page with Sign In / Register / Forgot-password tabs; auth guard in Shell; NavBar hides auth-required tabs for guests; Sign-out button; 401 interceptor. Rebuilt + deployed.
- DragonBones demo confirmed working in user's environment ("this is what we need" — Plan B greenlit).

### Follow-ups from 2026-05-10 Battle 3D Viewer v1

- [x] ~~**3 missing diorama themes**~~ ✅ Shipped 2026-05-10 PM. `cubicle-farm` (beige tan tint + 3×3 crate grid), `exec-floor` (gold tint + monolith + boss desk), `break-room` (pastel cyan + vending machine + coffee bar) composited from SciFi MegaKit primitives with `baseColorFactor` tinting. All 5 themes total ~830 KB. `STAGE_3D_THEME` now thematically maps all 26 seeded stages.
- [x] ~~**MeshBasicMaterial flash-white path**~~ ✅ Shipped 2026-05-10 PM. `flashWhite` now falls back to tinting `.color` when `.emissive` is absent (Quaternius druid). Hit reactions visible across all archetypes.
- [x] ~~**SPECIAL event defender visual**~~ ✅ Shipped 2026-05-10 PM. SPECIAL events now flash the attacker so the announcement has a distinct visual marker from a basic attack. (Defenders already get hit/flash via the follow-up DAMAGE events the special's effects emit — no defender-side gap exists.)
- [x] ~~**Real KayKit melee attack clip**~~ ✅ Shipped 2026-05-12. Migrated all 6 KayKit archetypes to Quaternius RPG Characters chibi pack (`maynewmodels/drive-download-20260509T192326Z-3-001/glTF/`). Each archetype now ships embedded per-class clips: `Sword_Attack` (knight/barbarian), `Staff_Attack` (mage), `Dagger_Attack` (rogue, rogue_hooded), `Bow_Shoot` (ranger). KayKit shared `kaykit_general.glb` + procedural arm-swing fallback both removed. Plan: `docs/superpowers/plans/2026-05-12-quaternius-rig-migration.md`.
- [~] **Engineer archetype model** — Monk rig (Quaternius RPG Characters) staged at `frontend/public/battle-3d/heroes/monk.glb` with full clipset (`Attack`/`Attack2`/`Idle_Attacking`/`Run`/`RecieveHit`/`Death`) registered in `clipMap.ts`. To wire: add `engineer: "monk"` to `scripts/gen-archetype-map.py::RIG_TO_ARCHETYPE` and assign the `engineer` rig name to a hero template in `app/rig_map.py`. Pure config change once a template wants it.
- [x] ~~**Real analytics sink for telemetry**~~ ✅ Shipped 2026-05-11 PM. `POST /telemetry/event` router forwards to `app.analytics.track` (PostHog wrapper; silent no-op until `HEROPROTO_POSTHOG_API_KEY` is configured). Frontend `battle3d/telemetry.ts` POSTs metrics with `fetch(..., keepalive: true)` so the call survives the lazy scene unmount; console mirror preserved for dev visibility. 5 tests in `tests/test_telemetry.py`.
- [ ] **Mid-battle wave-swap rig refresh** — `Battle3DScene` mount effect deps array is `[webglOk]` only. If multi-wave interactive battles ever ship, new units won't get rigs. Single-wave is the current contract; flag for revisit if the scope expands.
- [ ] **Three.js bundle split** — `Battle3DScene-*.js` chunk is 624 KB / 162 KB gz. GLTFLoader + DRACOLoader can be code-split further; Vite chunk-size warning ignored intentionally for v1. Revisit if mobile TTI on Slow 3G is too slow (target ≤3s).
- [x] ~~**Replace Throw fallback with procedural arm-swing**~~ ✅ Shipped 2026-05-10 PM, **obsoleted 2026-05-12** by Quaternius migration. `proceduralClips.ts` + its tests removed; real per-archetype melee/ranged clips now ship in each hero `.glb`.
- [~] **Monster select + team-builder UX overhaul** — partially shipped 2026-05-11 PM. `BattleSetupRoute` now has: tier-grouped collapsible stage selector with color-coded headers (NORMAL/HARD/NIGHTMARE/LEGENDARY palette matching `TierBadge`); rarity-tinted hero buttons + slot cards; role + rarity filter chips above the roster; 🕘 Last team / ⚡ Auto / 💾 Save preset / ✕ Clear action row; preset chips load from `/me/team-presets`; team-power vs stage-recommended delta tag (green/orange/red). Still open: drag-to-slot, faction synergy preview, dedicated TeamBuilder component if scope grows.
- [x] ~~**Interactive battle: target-pick clicks don't register in 3D mode**~~ ✅ Shipped 2026-05-11 PM. `Battle3DScene` now installs a `THREE.Raycaster` on canvas click + mousemove. Each loaded hero stamps `userData.uid` so the hit walks up the parent chain to find the unit. When `validTargets` includes the hit uid, the pointer cursor flips on hover and a click fires `onAct(uid)`. `propsRef` mirror lets the once-bound handler read the latest valid-targets / onAct without re-binding per render. HUD UnitCards continue to work in parallel.
- [ ] **Viewport-responsive 3D framing** — back-burnered 2026-05-11. Branch `feature/responsive-battle-3d` has a working `responsive.ts` that computes camera position + lookAt from viewport width / aspect, plus an `onResize` listener that recomputes live. Live test on 27" showed (a) the framing factor didn't move enough to be visibly noticeable when dragging across monitors, and (b) the wider-diorama / pushed-back changes that came with it lost characters again. Revisit: tune the responsive curve more aggressively, validate `container.clientWidth` actually updates on resize (suspected layout root may be locking width), and ship without the diorama auto-fit changes.
- [ ] **Explicit Attack / Skill / Limit action buttons** — back-burnered 2026-05-11. Backend (`app/interactive.py`) currently only takes a `target_uid` — there's no `action_type` parameter, so the HUD reuses target-click as "attack." Adding Skill/Limit buttons requires extending the API + combat resolver to honor an action-type selection, then a per-actor bottom-bar in `BattleHUD.tsx`.
- [ ] **Weapons on hero rigs** — back-burnered 2026-05-11. KayKit Hero Pack ships separate weapon meshes; need a per-archetype weapon→bone map (likely the right-hand wrist bone discovered the same way `proceduralClips.ts` discovers arm bones), and attach the weapon mesh as a child of that bone in `heroLoader.ts`. ~1-2 hours focused work once asset paths are confirmed.

### Follow-ups from 2026-05-07 rig work

- [x] **Move `TEMPLATE_TO_RIG` to backend `HeroTemplate.rig` column** ✅ 2026-05-08 (327c428). Migration `c7a91f3e4d2b` adds the column with stick-figure default + backfill from `rig_map.py`. `seed()` reconciles on every run. battles/arena/raids read `template.rig` directly.
- [x] **Nightmare difficulty seed** ✅ shipped in bfc23cd. 16 N-stages seeded via the same `STAGE_SEEDS` loop (+20 levels, 2.5x rewards, gated on Hard clear).
- [x] **Stage tier icons (NORMAL / HARD / NIGHTMARE)** ✅ shipped in bfc23cd (`frontend/src/components/TierBadge.tsx`, used in Stages route + BattleSetupRoute).
- [x] **Slice ninja-monk + ninja-peasant frames look short next to others** ✅ shipped in bfc23cd via `scripts/pad_ninja_frames.py`.
- [x] **Delete `app/static/heroes/sprites/` rigged paper-doll parts** ✅ shipped in bfc23cd (~150MB pruned).

### Next session

- [ ] **Real-device Android field test.** Emulator pass logged in `docs/ANDROID_FIELD_TEST_2026-05-17.md` (verdict PARTIAL — bundle healthy, lobby renders, battle UX not exercised). Need a real phone to verify: in-app sign-in form, DEPLOY → battle flow, action bar touch targets, damage numbers + quip toasts at narrow CSS width, turn-order ribbon legibility, Battle 3D GPU profile, back button → React Router, shop SKU gating, BP purchase messaging. Also flag-bug for the day: hard-nav to sub-paths breaks Capacitor relative asset resolution (4 fix candidates noted in the doc).

### Known papercuts still open

- **Postgres compose-stack smoke: PASSED 2026-05-05.** STARTUP CHECK OK (3 warn/expected, 6 ok) + CLIENT WALKTHROUGH PASSED (34 sections) against postgres:16-alpine. Fixed three script bugs in the process: register expected 201 (returns 200), env was `dev` so email-verify gate blocked summons (now `test`), worker reported `enabled:true` in test mode when task wasn't started (now `false`). Run: start Docker Desktop, then `bash scripts/postgres_stack_validate.sh`.
- ~~**Production rigs**~~ ✅ **Resolved 2026-05-07** — CraftPix pre-rendered PNG-frame pipeline replaces the abandoned DragonBones/Moho path. 26 rigs live, each hero template mapped, bust portraits + backgrounds wired across all stages and difficulty tiers.
- **SPA shipped ✅** — React SPA is the primary client. Vanilla-JS shell still exists at `/app/partials/*` and the admin panel; those are not yet ported to React. Next: Event tab missing from SPA nav (no nav tab for `/app/event`, only appears when event is active via the event query). Admin panel is still vanilla-JS.

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
- ~~Battle viewer needs animated actors.~~ ✅ **Shipped 2026-05-10** for interactive mode (Three.js + KayKit chibi rigs). Instant-replay still uses CraftPix PNG-frame pipeline in `battle-arena.html`.
- ~~**Stick figures are fine as placeholders**~~ ✅ Replaced by KayKit chibi 3D models for interactive mode.
- Current SVG portraits stay on roster/replay cards; battle stage now has its own 3D animated layer (interactive) or PNG-frame layer (replay).

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

## 🎯 Phase 2 — shipped 2026-04-26 ✅

Phase 1 is done. The product is now genuinely playable for a new user — tutorial flow, visual roster, team presets, dedicated Summon tab, starter pack. Phase 2 ("Feels like a real game") per `docs/PRD.md § 7` is now mostly shipped:

- **2.1 Hero detail depth ✅** — per-slot WEAPON/HELMET/ARMOR/BOOTS/RING/AMULET shipped pre-Phase-2; star-up via `/heroes/{id}/ascend-with-shards`, special-up via `/heroes/{id}/skill_up` (both shard-based post 2026-05-12 remap; fodder paths removed). Phase 2 closer: `GET /heroes/{id}/preview` returns level-up / star-up / special-up projections (current vs after stats + delta + cost) gated on shard balance. UI can render "+10% power with one more copy" teasers from this. 6 tests in `test_hero_upgrade_preview.py`.
- **2.2 Event content + dupe variance ✅** — Myth-tier wired end-to-end (TBFAM, Mother's Day Applecrumb event); scheduled future LiveOps via admin POST `/admin/liveops` w/ `starts_at` + `GET /liveops/scheduled?horizon_days=N`. Stat variance on duplicate summons: `HeroInstance.variance_pct_json` rolled triangular ±10% per stat on dupes only (first copy stays vanilla); applied in combat + roster. 5 tests in `test_stat_variance.py`.
- **2.3 Analytics ✅** — PostHog wrapper at `app/analytics.py`, 12 events instrumented, RUNBOOK §Analytics, `scripts/verify_analytics.py` smoke tester, `scripts/posthog_dashboard.json` 10-insight starter. **Last step (ops):** set `HEROPROTO_POSTHOG_API_KEY` in prod, run verify_analytics from staging, import dashboard, run client_walkthrough.
- **2.4 Store expansion ✅** — Apple StoreKit + Google Play Billing adapters in `app/payment_adapters.py` (real-mode lazy-imports SDKs; sandbox-mode shortcut for `fake-apple:`/`fake-google:` receipts). Endpoints `POST /shop/iap/{apple,google}` already wired. Phase 2 closer: PoE2-style QoL/cosmetic catalog — auto_battle, extra_team_presets, quick_summon, roster_sort_advanced; +25 hero / +100 gear slot packs (stackable); 4 cosmetic frames + a frame bundle. New `KNOWN_QOL_UNLOCKS` / `KNOWN_COSMETIC_FRAMES` registries in `app/store.py`; restore-purchases idempotent; misconfigured codes raise loudly. 8 tests in `test_iap_and_qol.py`.
- **2.5 Story + account XP + EXILE ✅** — `app/account_level.py` ships triangular XP curve, level-up rewards, 3 story chapters (Onboarding / Middle Management / Executive Floor) with cutscene beats. `app/routers/story.py` exposes `GET /story` + `POST /story/cutscene-seen`. Phase 2 closer: EXILE faction enum value + `Account.faction` column defaulting to EXILE for all new players (Phase 3 will flip this to RESISTANCE / CORP_GREED at the level-50 alignment fork). 3 tests in `test_exile_faction.py`.

- **2.6 Balance tooling ✅** — `analytics/` directory with three runnable notebooks: `gacha_ev.ipynb` (per-pull EV bar chart + pulls-to-first-EPIC histogram), `combat_dps.ipynb` (DPS proxy by hero at level 30), `arena_convergence.ipynb` (rating trajectories across 4 true-skill bands). Each notebook imports from `app/` directly so balance changes flow through on next run. Output PNGs committed to `analytics/output/`. Smoke-tested in `tests/test_balance_notebooks.py` (3 tests) so a symbol rename in `app/` breaks a fast unit test instead of a notebook.

**Phase 2 review fixes (2026-04-26)** — gaps caught in a post-shipment audit:
- **Myth-tier event banner ✅** — `LiveOpsKind.EVENT_BANNER` + `POST /summon/event-banner` (+ GET status). Per-account cap stored on `event_state_json`, gated strictly on active LiveOps window. Mother's Day event JSON now seeds the Applecrumb banner alongside DOUBLE_REWARDS. 7 tests in `test_event_banner_summon.py`.
- **Story chapter-end rewards ✅** — `maybe_grant_chapter_reward()` fires on first_clear of a chapter's last stage, idempotent via `story_state_json.chapter_rewards_claimed`. Wired into the /battles flow. `/story` exposes `completed` / `reward_claimed` / `end_reward`. 4 tests in `test_chapter_rewards.py` (1 flaky-skip from RNG-dependent battle path).
- **End-to-end acceptance test ✅** — `tests/test_phase2_acceptance.py` exercises EXILE default → preview endpoint → variance round-trip → analytics recorder → Apple+Google IAP → story chapter unlock + reward → Myth event banner gating in one flow. Mirrors `test_phase1_acceptance.py` pattern.

Phase 3 (combat depth) is next-arc — see `docs/PRD.md § 8`.

---

## 🎯 Legacy sprint backlog (pre-PRD scoping)

Each sprint is sized to be shippable in one session. Pick one; don't interleave.

### A. Frontend polish
The dashboard works; nobody wants to look at it. Biggest perceived-quality lift per hour.
- [x] CSS pass on `/app/*` — `app/static/style.css` adds faction tokens (`--faction-*`), MYTH rarity (`--r-myth`), mobile nav scroll, stat/progress/badge components. Linked from `base.html`.
- [x] Error toasts — `app/static/toast.js` provides `toast.error/success/info(msg)`; bottom-center stack, color-coded by kind, auto-dismiss (errors 5s, others 3.5s), tap-to-dismiss; replaced 9 `alert()` callsites in friends/stages/story partials + battle-setup/roster static pages
- [x] Loading states — shared `.skeleton` / `.skeleton-line` / `.skeleton-grid` utilities in shell.html + initial `#content` placeholder + reuse in account/raids partials. Per-section refinement (every partial gets its own shimmer skeleton matching its layout) is still open as a polish pass.
- [x] Mobile-responsive layout — nav scrolls horizontally on mobile (no hamburger needed), header compacts below 640px, `#who` pill hidden on small screens
- [x] Rewrite as a real SPA — React + Vite SPA shipped, all routes wired, auth guard, register/forgot-password on login page, Sign-out in nav, 401 interceptor

### B. Anti-cheat depth
One layer shipped (per-account battle rate limit). More to add.
- [x] Cap arena attack attempts per hour — `arena_attack_per_minute_per_account=20` enforced via `enforce_arena_rate_limit`
- [x] Audit all endpoints for `hero_instance_id` ownership check — 7 guard tests in `test_cross_account_ownership.py`
- [ ] Reject implausible combat outcomes (still blocked on a client-authoritative layer; not actionable yet)
- [x] Per-IP guild-message rate limit — `enforce_guild_message_ip_rate_limit` in chat dependencies, Redis-backed under horizontal scale

### C. Deploy pipeline
Dockerfile + compose exist; nothing's been pushed or deployed.
- [x] Run `scripts/postgres_stack_validate.sh` once green — PASSED 2026-04-27. All 17 walkthrough sections OK against postgres:16-alpine. 2 expected warns (admin creds not set, Stripe not configured). — **BLOCKER 2026-04-26: Docker Desktop installed but daemon not running; start Docker Desktop and retry**
- [x] Build + push Docker image to a registry — Fly.io builds & stores the image as part of `fly deploy` (Dockerfile is the build context)
- [x] Pick a hosted target — Fly.io chosen, app `hero-proto` already deployed during admin-lockdown sprint
- [x] Automated daily DB backup — `scripts/backup_db.sh` handles SQLite (sqlite3 .backup + gzip) and Postgres (pg_dump custom format), date-stamped names, RETAIN-based pruning, run from cron/systemd-timer
- [x] Graceful shutdown — worker cancels + in-flight battles finish (lifespan handles it; documented in RUNBOOK with uvicorn flag recommendations)

### D. Raid depth ✅ done (2026-04-25)
Raids work; they're shallow.
- [x] Scheduled raid auto-start — `_auto_rotate_raids()` in `app/worker.py` (already shipped)
- [x] Per-attempt cooldown — `RAID_ATTEMPT_COOLDOWN_SECONDS = 600` enforced in `attack_raid` (already shipped)
- [x] Leaderboard endpoint — `GET /raids/leaderboard?days=7&limit=25`, public, in `app/routers/raids.py` (already shipped)
- [x] Unique boss-only specials — new `BOSS_PHASE` special type; 3 raid bosses re-tuned to use it with HEAL_BLOCK / FREEZE / BURN + self REFLECT/ATK_UP. See "Sprint D close (2026-04-25)" below.

### E. Observability next steps
- [x] OpenTelemetry tracing (propagate request IDs into spans)
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
- [x] Melee / ranged attack split — Phase 3.1 shipped: `HeroTemplate.attack_kind` ('melee'|'ranged') + `channel` on DAMAGE log events. Replay viewer wired (Phase 3.3): melee → lunge animation; ranged → `_rangedAttack()` projectile arc (cyan circle travels attacker→target, damage on arrival).
- [x] Mana or spell-point resource for ranged/magic heroes — Phase 3.2 shipped: `HeroTemplate.mana_cost` (default 10) + `mana_regen_per_turn` (default 15) columns + migration `d515d104feb9`. Ranged units skip basic attack on 0 mana (MANA_EMPTY logged); regen fires at turn start capped at `mana_cost * 5`. Melee units unaffected. 4 tests in `test_phase3_combat.py`.
- [x] Hail-mary ability at ≤5% HP — role-flavored, one-shot per battle.
- [x] Player control during battle (target selection / turn pause) — target priority shipped (Phase 3.2). Per-turn interactive mode shipped (Phase 3.3): `simulate_interactive()` generator + in-memory session store + `POST /battles/interactive/start` + `POST /battles/interactive/{id}/act` + same endpoints for raids + `battle-interactive.html` UI + "Play Turn by Turn" toggle on battle setup. 10 tests in `test_interactive_combat.py`.
- [x] Animated actor layer for battle viewer — **shipped 2026-05-03**. Dropped DragonBones (Moho pipeline abandoned). Replaced with pre-rendered PNG frame sequences from the Dark Assassin animation pack (Spine 3.8 export, 352 frames across idle/attack/hurt/die/run). All units use the animated rig; role tinting via CSS drop-shadow — ATK=red glow, DEF=blue glow, SUP=gold glow. COF SVG backgrounds (9 stages) wired in. No runtime dependency, works in any browser. Registry updated at `app/static/battle-rigs/registry.json`.
- [x] Auto-battle as a paid QoL unlock — `qol_auto_battle` SKU + `auto_battle` flag in qol_unlocks_json + `auto: true` flag on POST /battles + `auto_resolved` echo + skip-watch UI.

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
- [x] ~~**Stick-figure battle animation sprite sheets**~~ — superseded 2026-05-07 by CraftPix PNG-frame pipeline. 26 rigs live, every hero template_code mapped, idle/attack/hurt/die/run animations all working in prod.
- [ ] **App icon + maskable PWA icons** — unblocks Sprint H. 192×192, 512×512, maskable-safe (80% inner keep-clear), 1024×1024 for Apple touch icon.
- [ ] **Roster card redesign mockups** — current is a list, we want rarity-tabbed grid with faction/role/power/upgrade-teaser per hero. Figma or annotated PNG.
- [ ] **Shop page mockups — PoE2-style** — layout for gem packs, QoL packs, cosmetic frames, seasonal offers. Tone: premium/optional, not FOMO.

### Medium leverage
- [ ] **Missing hero portraits** — roster currently has 35 heroes; any generic/placeholder slots that need art. Request: faction-tinted backgrounds, role-suggestive poses.
- [x] ~~**Stage background set**~~ — done 2026-05-07. All 16 normal stages + 13 story arcs + 3 raid bosses mapped in `STAGE_CODE_TO_BG`, with `H-` prefix strip so Hard tiers share their base bg. Verified live on First Ticket / Onboarding Day / First Outage / Quarterly Audit / Legacy Server Room.
- [ ] **Raid boss art** — bosses now have battle rigs (minotaur-1/minotaur-3/red-werewolf) and busts via `template_code`, but the **hero-card art** for the raid landing page is still placeholder. Animated hit-reaction layer also pending.
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
- [x] Admin UI over the existing `/admin/*` endpoints — `/app/admin` (2026-04-26)

### Auth / account
- [x] Account data export (GDPR art. 20) — `GET /me/export`, e2d2ff5
- [x] Login history / active sessions list — `GET /me/sessions` + revoke endpoints, e2d2ff5
- [x] Device fingerprinting for refresh-token anomaly detection — `fingerprint_hash` (sha256 of UA|IP) on RefreshToken, compared on rotation. Mismatch logs `auth.refresh` warning + bumps `refresh_token_anomaly_total` Prometheus counter; never auto-revokes (legit users roam, browsers update). 4 new tests cover persist + match + mismatch + null-legacy paths.
- [x] **Speed up email delivery (forgot-password, verification).** Root cause was SMTP send blocking the HTTP response (1-5s round-trip on Fly). Fixed 2026-05-05: all auth email sends now use FastAPI `BackgroundTasks` — email is rendered inline (fast), response goes out immediately, SMTP fires after. Remaining ops steps if inbox latency is still noticeable: (1) switch to Postmark (`HEROPROTO_EMAIL_SMTP_*` secrets only, no code change), (2) verify SPF + DKIM on `HEROPROTO_EMAIL_FROM_ADDRESS` domain.

### Guilds
- [x] Promote / transfer endpoints — `/guilds/{id}/{promote,demote,transfer,kick}/{account_id}` already shipped
- [x] Application flow — `/guilds/{id}/apply` + `/guilds/applications/{id}/{accept,reject}` already shipped
- [x] Invite flow — `GuildInvite` model + 6 endpoints (invite/accept/reject/cancel/list outgoing/list mine), 10 lifecycle tests. See "Guild invite flow (2026-04-25)" below.
- [x] Soft-delete for direct messages — sender-only `DELETE /dm/{id}`, body redacted to `[deleted]` in /dm/with/* + /dm/threads, row stays so reports/audit resolve. Migration `177a30b78d4a`.
- [x] Per-guild achievements / milestones

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
- [ ] **Brainstorm Exile + other races** — what races/origins exist in the world, how they slot into the alignment fork (light/dark), unique mechanics or stat profiles per race, naming + lore hooks. Exile is the seed concept; expand outward from there.
- [ ] **Wire alignment-themed BGM** — 6 tracks staged in `sound/` (3 dark / 3 light), pick stage/scene mappings.
  - **Dark side** — `Abyssal_Echoes.mp3`, `Wrath_of_Ares.mp3`, `dark_dungeon_music.mp3`
  - **Light side** — `Cartoon_Chaos_Fast-Paced_Chase_Scene_Music.mp3`, `Mischief_Maker.mp3`, `The_Ancient_Map_-_Epic_Fantasy_Adventure_Trailer.mp3`

### Combat
- [x] More status effects (FREEZE / BURN / HEAL_BLOCK / REFLECT) — see "Combat depth (2026-04-25)" below
- [x] Faction affinity / synergy bonuses — 3/4/5-of-faction tiers, baked into base_atk/base_def before sim
- [x] AoE revive — new `AOE_REVIVE` special type, respects HEAL_BLOCK on corpses
- [x] Combat log pruning — `trim_combat_log()` already in place at 200-entry cap

### Infrastructure
- [x] Postgres end-to-end smoke (Sprint C) — PASSED 2026-05-05. STARTUP CHECK OK + CLIENT WALKTHROUGH PASSED (34 sections). Run anytime: start Docker Desktop, then `bash scripts/postgres_stack_validate.sh`.
- [x] Docker image build + push to a registry — Fly.io builds + stores the image on every `fly deploy`
- [x] Automated daily DB backup — `scripts/backup_db.sh` (see Sprint C above)
- [x] Graceful shutdown — worker cancels + in-flight battles finish (lifespan handles it; documented in RUNBOOK with uvicorn flag recommendations)
- [x] Deploy target picked — Fly.io, app `hero-proto`
- [ ] **Android keystore hardening** — current release keystore was generated with a moderate password. Two paths before production Play Store submission:
  1. **Play App Signing (recommended)** — Google holds the distribution key. We keep an *upload* key (the existing keystore is fine for that role). On first upload to Play Console, opt into Play App Signing; Google generates a new signing key, we keep using `release.keystore` to sign uploads. If `release.keystore` is ever lost, Google can rotate the upload key — no impact on the published app's signature. **This is the path to take.**
  2. Re-key with a stronger password — requires uninstall + reinstall by every existing user; only worth it pre-launch if we change our minds about (1).
  - Either way, before the first signed upload: rotate the upload-key password to ≥20 chars random and update the GitHub Actions `ANDROID_KEY_PASSWORD` / `ANDROID_KEYSTORE_PASSWORD` secrets accordingly. Until first store submission this is informational only.

### Observability
- [x] OpenTelemetry tracing (propagate request IDs into spans)
- [x] Alerting thresholds documented (5xx rate, p99 latency, worker, 429s, purchases, webhooks, token revocations, throughput drops) with PromQL — `docs/RUNBOOK.md`
- [ ] Dashboard screenshots in `RUNBOOK.md` — layout drafted; capture once prod has real traffic

### Anti-cheat / validation
- [x] Per-account rate limit on `/battles` (Sprint A)
- [x] Cap arena attack attempts per hour — `arena_attack_per_minute_per_account`
- [x] Audit all endpoints for `hero_instance_id` ownership check — e2d2ff5, 7 guard tests
- [x] Per-IP guild-message rate limit — e2d2ff5 (per-IP bucket, Redis-backed when configured)
- [ ] Reject combat outcomes that couldn't happen (if client-authoritative layer ever gets added)

### Localization
- [x] Message catalog (gettext-style) for user-visible strings
- [ ] Hero/skill-name translation fields on `HeroTemplate`
- [x] `Accept-Language` header handling

### Payments
- [x] `OfferBundle` table (premium shard bundles, starter packs)
- [~] Purchase history / refund flow UI — `GET /me/purchases` done (paginated history with product_code/amount_usd/payment_method); refund UI follow-up still open
- [~] Anti-fraud basics (velocity limits, device fingerprint) — velocity limiting done (5 bundle purchases/hour, DB-counted); device fingerprint on refresh tokens also done; payment-side device fingerprint follow-up still open
- [ ] Subscriptions / monthly pass

### Frontend
- [x] Real SPA (React + Vite) — shipped, all routes, auth guard, full login/register/forgot-password flow
- [ ] CSS + loading/error states — SPA uses inline styles; a shared stylesheet pass would tighten consistency
- [x] Mobile-responsive layout ✅ — `NavBar.tsx` collapses to hamburger drawer below 720px; `.nav-strip` hidden, `.nav-hamburger` shown via media query (global.css:361).
- [x] PWA offline shell ✅ — `vite-plugin-pwa` registered with autoUpdate workbox SW; manifest + maskable 512 icon already wired in `frontend/vite.config.ts`.
- [x] Native iOS / Android wrapper (Capacitor) — Android running on emulator; iOS via cloud CI

### Progression system (5 subsystems, sequenced)
Specs at `docs/superpowers/specs/2026-05-09-*.md` (5 design docs from 2026-05-09).
- [x] **#1 Difficulty tiers** ✅ shipped 2026-05-09 — 4-tier system (Floppy/Hard Disk/RAID-0/Legen'waitforit'dary), XP 12/28/50/60, level deltas +0/+10/+20/+30, seed produces 4 tiers × 26 stages = 104 rows. Plan: `2026-05-09-difficulty-tiers.md`.
- [x] **#2 Tier locks + power floor** ✅ shipped 2026-05-09 — `app/tiers.py` with TIER_POWER_FLOOR (50k/100k); battle-start guard with HTTP 400 + required/current detail; `/stages` now auth'd with unlocked/cleared/power_floor fields; frontend lock + floor badges. Plan: `2026-05-09-tier-locks-power-floor.md`.
- [x] **#3 Fail pity** ✅ shipped 2026-05-09 — `app/fail_pity.py` (PITY_LOSS_THRESHOLD=3, PITY_HP_MULT=0.9); `accounts.stage_pity_json` column + migration; wired into battles.py (start applies HP mult, end updates count). Hidden — no UI surfacing. Plan: `2026-05-09-fail-pity.md`.
- [x] **#4 Rest XP** ✅ shipped 2026-05-09 — `app/rest_xp.py` (12h cap, 2x burn, 5min idle threshold); 2 columns + migration; ticked via `get_current_account`; multiplier in `grant_xp` + at 2 hero-XP call sites (battles/AFK); rested badge in /me. Plan: `2026-05-09-rest-xp.md`.
- [x] **#5 Drop meter** ✅ shipped 2026-05-09 — `app/drop_meter.py` (cap=20, tier-keyed RARE+ guarantee pool); `accounts.stage_drop_pity_json` column + migration; wired into 3 battle drop sites; meter+cap surfaced via /stages; "Drop in N" badge on stage rows. Plan: `2026-05-09-drop-meter.md`.

### Onboarding quest system ✅ shipped (verified 2026-05-09)
- [x] Backend: `Quest` + `AccountQuest` models, `app/quest_service.py` `record_event()`, `/quests/active` + `/claim` + `/dismiss` in `app/routers/quests.py`, seed in `app/quests.py`, auto-enroll in `auth.py:register`
- [x] `record_event` hooks wired across battles, summon, gear, arena, guilds, daily, story, me, raids (all 11 spec events)
- [x] Frontend: `frontend/src/components/QuestWidget/{index,ClaimModal}.tsx` mounted in `Layout/Shell.tsx`
- [x] Coach marks: `components/CoachMark.tsx` + `localStorage` tracking, wired in Stages, Summon, Inventory, Arena, Guild, Daily, Roster (7 screens)
- [x] Tests: `tests/test_quests.py` — 6/6 passing
- [x] ~~Legendary stage tier doesn't exist in `StageDifficulty` enum~~ — resolved 2026-05-09 by progression subsystem #1 (LEGENDARY enum + 26 LEGENDARY stage rows seeded).
- [x] ~~Faction choice unlock at lvl 50 vs onboarding task~~ — resolved 2026-05-09 by removing the `faction_chosen` task from week-one quest. FACTION_CHOSEN was structurally unreachable for new accounts (alignment is a lvl-50 chapter-4 milestone, not an onboarding step). Quest now 18 tasks.

---

## 🎮 Engagement / monetization design (research-driven, captured 2026-05-09)

### Daily / weekly events — *Battle of the OSs* (concept)
- [ ] Daily event popup; week-long quest examples themed to hero-proto's mixed-hardware/mixed-OS premise
- [ ] Example arc: **Battle of the OSs** — random "parts" drop from stages, player assembles a working system to defeat **Boto** (boss/bot — name TBD)
- [ ] Different events spotlight different stacks; ties into roster's IT-flavor identity
- [ ] Pairs with collections (below) — events drive seasonal grind, collections drive long-term grind

### Rare collections v1 ✅ shipped 2026-05-10
- [x] 12 collections seeded (4 rarities × 3 brackets: 1-20, 21-40, 41-60)
- [x] Drop pipeline wired in 3 battle sites (fight/sweep/auto-resolve) + 5% raid contribution rate
- [x] `/collections` API: GET list, POST claim, POST 8-track/open
- [x] 8-track grants from weekly chest (per ISO week), tower floor-50 first-cross, raid top-10% per raid
- [x] Frontend: Collections.tsx grid route + nav entry; loot popup component shipped (battle-flow wiring deferred to v1.1); `/me.eight_tracks` surfaced
- [x] Tests: 24/24 passing in `tests/test_collections.py`
- [ ] **v1.1 polish**: wire CollectionLootPopup into battle response flow; coach-mark trigger on first piece drop
- [ ] **v2 follow-ups**: Legendary set-bonus passive design (replace placeholder reward), Myth tier RNG-gated unlock on Legendary completion, buyable 8-tracks via Stripe SKU, random collection-piece rotation in shop catalog. Spec deferrals listed in `docs/superpowers/specs/2026-05-10-rare-collections-v1-design.md` §11.

### Battle viewer #3 — full Three.js overhaul (backburner)
- [ ] Replace `battle-arena.html` with Three.js scene using KayKit GLTFs from `maynewmodels/`
- [ ] Combat resolver stays unchanged — only the renderer changes
- [ ] Active direction is **#1 + #2 hybrid**: pre-render KayKit/PSX into CraftPix-shaped sprite frames + Three.js viewer for interactive mode
- [ ] "Easy to whip up when we get time" — not blocking anything

### Competitor playbook (MSF / SWGOH / PortalQuest / DandyDungeon / DragonChampions)
*Full intel: Phase 1 + Phase 2 store sweeps complete 2026-05-09. Recurring intel feed.*

**⚠️ Attribution corrections caught in Phase 2:** Portal Quest = PerBlue, NOT NimbleBit (real PerBlue postmortem = Disney Heroes Battle Mode shutting May 31, 2026 with $110K/mo revenue insufficient under Disney IP fees). Dragon Champions = PlayQuantum/AppQuantum, NOT Crazy Panda — zombie state, not delisted.

**Cross-cutting lessons:**
- Never invalidate earned progression (MSF OVERPOWERED, SWGOH Era/Relic Delta)
- Pop-up shop interruption = uninstall (15-min new-player churn)
- Guild raids carry retention but must scale to small guilds (4–6 active)
- F2P viability is the marketing truth — lead with "you don't have to spend"
- Production value > feature breadth (DragonChampions died feature-complete)
- UA war on Play Store unwinnable vs RAID's $100M+ — web-first/Stripe sidesteps it
- Theme is the differentiator. First 10 min must communicate why we're not RAID

**Paywall anatomy (the throughline — every churn vector traces here):**
- MSF shard-pack deception: $50 = unlock only, not max-star (43% of 1★ reviews)
- MSF spend-tier inflection: $20-35 minnow churn / $50-100 dolphin / $300-500 mid-whale / $10k+ terminal-whale "I quit"
- MSF betrayal window: Year 2-3 (sunk cost becomes weapon when new tier obsoletes portfolio)
- SWGOH disguised subscription: $20/mo Episode Pass + ~$40/mo Pass+ + $150-200/Era character → de-facto recurring without disclosure
- SWGOH quantified churn: 50K MAU in 2 weeks after Overpower (Apr 2025), ~10K/mo sustained
- DandyDungeon counter-data: "ducks IAP" — friction → purchasable removal → upgrade-to-ownership feel
- Premium-feel vocabulary: *polished* / *respects your time* / *no nag* / *worth every penny*

**Economy design principles (locked):**
1. **Golden Ratio** — F2P maxes a hero in 30 days; minnow does it in 15 for $5. Purchase = time-saver, not gate.
2. **Power Creep Trap** — Linear effort growth, exponential cost growth (lvl 1→10 = 100g, lvl 10→20 = 500g). Soft walls drive spend over spike.
3. **Pity is mandatory** — Pure RNG hurts business. Pity at 9 → guaranteed at 10. Turns gambling into progress bar.
4. **Currency tiering** — Soft (gold, plentiful), Hard (gems, real money / bypass time), Social/Event (earned with others — keeps F2P logged in so whales have someone to play against).
5. **Minnow Daily Login Pass** — $4.99 / 30 days of small rewards. Highest value/$ in game. Forces daily login → builds habit.

**Open question (parked):** Hero-proto already runs BOTH gacha summons + template-shard ascension. Tune them together so neither dominates — dedicated design pass when monetization is ready for calibration.

### DO / DON'T — Marketplace + Player-Base design rules

*Distilled from research above. Apply when designing any shop, IAP, BP, monthly card, event, raid, arena, or community feature.*

**Marketplace — DO:**
- ✓ Make every purchase **atomic** (buying a hero gives the hero, not 47/100 shards). If shards involved, show count + total cost before confirmation.
- ✓ BP/card unlock = ownership moment. Visible state change (badge, color shift, "Welcome Supporter"). Not a receipt.
- ✓ Suppress all gacha/IAP promos during active BP or monthly card. Reintroduce at renewal only.
- ✓ Frame BP/card as "the ducks", not "a subscription". Vocabulary: polished, respects your time, no nag.
- ✓ Every event has a guaranteed F2P ceiling at ~70% of milestone track. Spend-gated rewards live in the top 30%.
- ✓ Honor every payment failure with auto-grant within 24h. No ticket required.
- ✓ Keep all IAP through platform storefronts. Don't route around Apple/Google.
- ✓ Audit "fully-activated competitive player" monthly spend — if total > $30/mo AND necessary for PvP viability, you have the disguised-sub pattern.
- ✓ Storefront = single entry point. Never interrupt navigation with shop popups.

**Marketplace — DON'T:**
- ✗ NEVER add a new tier to existing progression mid-life that invalidates prior spend. (#1 whale-churn trigger.)
- ✗ NEVER sell a direct combat-stat multiplier to a subscriber tier (the OVERPOWERED failure). VIP/BP/card may gate cosmetics, currency drip, convenience — never raw combat math.
- ✗ NEVER cap PvP performance by spend level (Relic Delta failure).
- ✗ NEVER lock new characters behind a 3-month time gate after launch.
- ✗ NEVER narrow daily/streak windows below 24 hours.
- ✗ NEVER de-surface free progression after a purchase ("Find" button shifting to shop after spend).
- ✗ NEVER front-load monetization at launch (DragonChampions: $1M month one → collapse).
- ✗ NEVER promise content cadence you can't keep (Portal Quest died from this).

**Player-Base — DO:**
- ✓ Design guild raids for **4–6 active members minimum**, not 20.
- ✓ Reply to store reviews. Free retention signal.
- ✓ Lightweight balance pass cadence on PvP/arena.
- ✓ Match arena/PvP by account XP/power score, not raw rating.
- ✓ Surface faction/team synergy in roster UI — synergy is the gacha equivalent of a progress bar.
- ✓ Make the IT-theme louder in the first 10 minutes.
- ✓ AFK/idle income should be **diegetic** ("your squad has been grinding" >>> "Offline earnings: 847 coins").
- ✓ Build social features that retain even when they don't directly monetize.

**Player-Base — DON'T:**
- ✗ DON'T proliferate servers to solve retention. Splits playerbase, fragments social graph.
- ✗ DON'T make F2P viability ambiguous. Positive reviews lead with "you don't have to spend."
- ✗ DON'T let "fine" be the production-value bar. Acceptable art in a premium-art genre = invisible.
- ✗ DON'T release new heroes faster than the 6★ ascension system can absorb. Depth > breadth.
- ✗ DON'T have a single resource bottleneck. Resources must drain at the rate they generate.
- ✗ DON'T treat your playerbase as a UA cohort. Long-tenure players ARE the most monetarily valuable AND the highest churn risk.
- ✗ DON'T let raids degrade into "log in and simulate". Strategy layer = social glue.
- ✗ DON'T put the angry whale letter at the top of your reviews. Reluctant whales who spent $10k+ then quit angry = worst possible monetization outcome.

**Hero-proto-specific safeguards (from research):**
- BP + monthly card structurally protect against MSF/SWGOH "OVERPOWERED" failure mode IF kept opt-in and non-stat-gating
- Tower of Trials addresses Portal Quest's biggest gap (no endgame loop)
- Guard against future scope creep that bolts on a new monetization layer mid-life — that's the exact moment MSF lost its 2-3 year cohort

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
- [x] Docker container smoke ✅ — `scripts/postgres_stack_validate.sh` builds the stack, probes `/healthz` + `/docs`, then runs the full startup-check + client-walkthrough.
- [x] `smoke_guild.py` / `smoke_raid.py` E2E mirrors of the unit tests ✅ — `smoke_raid.py` shipped 2026-05-08 (e836511).
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

**Phase 2 review fixes (2026-04-26)**
- Myth-tier event banner: `LiveOpsKind.EVENT_BANNER` + `POST /summon/event-banner` (per-account cap, active-window gating). Mother's Day Applecrumb banner now reachable.
- Story chapter-end rewards: `maybe_grant_chapter_reward()` wired into /battles, idempotent via story_state_json, gem rewards scaled per chapter.
- `tests/test_phase2_acceptance.py` — full PRD § 7 acceptance flow.

**Phase 3.5 — Alignment Fork (2026-04-29)**
Level-50 one-time faction choice: EXILE → RESISTANCE or CORP_GREED. Permanent, idempotent, gated.
- `Account.alignment_chosen_at` nullable DateTime + alembic migration `06604894e633`.
- `Faction.RESISTANCE` + `Faction.CORP_GREED` added to enum (were placeholders).
- Two exclusive EPIC heroes seeded (excluded from summon pool, same as MYTH):
  - The Whistleblower (RESISTANCE SUP) — Leak The Memo: AOE ATK buff + DEF down
  - The Successor (CORP_GREED ATK) — Hostile Takeover: AOE damage + HEAL_BLOCK + self ATK up
- 10 new story stages (resistance_breach → resistance_aftermath, corpgreed_first_move → corpgreed_apotheosis).
- Two new Chapters in `STORY_CHAPTERS` with full cutscene content (`required_alignment` field gates visibility by faction; EXILE players see neither until they choose).
- `ALIGNMENT_CHAPTER_HERO` dict + `_grant_alignment_hero()` — creates HeroInstance of exclusive hero on chapter completion, idempotent.
- `maybe_grant_chapter_reward()` extended: calls hero grant, returns `hero_granted` in result.
- `chapter_status_for_account()` filters alignment chapters by `account.faction`; exposes `required_alignment` + `alignment_hero` in output.
- `CHAPTER_END_REWARDS` extended (1200 gems + 300 shards + 8 cards + 8 credits per alignment chapter).
- `POST /story/alignment` — validates level ≥ 50, faction == EXILE, not-yet-chosen; sets faction + alignment_chosen_at + fires notification; 403 < lvl 50, 409 if already aligned.
- `MeOut` schema gains `alignment_chosen_at: datetime | None`; `/me` router maps it.
- Arena `list_opponents`: `_build_stmt()` helper; same-faction pool tried first for RESISTANCE/CORP_GREED, falls back gracefully to any-faction.
- Frontend: `types/index.ts` adds `faction` + `alignment_chosen_at` to `Me`; `api/story.ts` fully typed + `chooseAlignment()` call; `Story.tsx` overhauled (AlignmentFork card, ChapterCard with stage list + cutscene previews + faction coloring); `Me.tsx` FactionBadge component in profile banner.
- 11 tests in `tests/test_alignment.py`. Suite: 621 passed, 3 skipped.

**Phase 2 polish + Phase 3.1/3.2 starters (2026-04-26)**
- **Bug-fix batch from human-test (`docs/PHASE_2_HUMAN_TEST.md` #1-#8):**
  - #1/#4 cross-account session leak — centralized `heroSetAuthSession`/`heroClearAuthSession` helpers in `base.html` wipe per-account `localStorage` and clear `#content` on every login/register/logout/401. Wired through login.html, account.html (revoke-all), welcome.html, reset_password.html, static/index.html.
  - #2 summon recent-pulls stale — `summonFromTab` inline-prepends to `#summon-recent-grid`; full tab refresh shortened from 1200ms → 600ms.
  - #3 sweep 422 + `[object Object]` — `SweepIn.team` now optional with fallback to last winning team; new `toast.formatErrorBody()` + `toast.fromError()` pretty-print Pydantic 422 lists.
  - #5 post-mortem polish — battle result shows bust portraits + name + level + currency reward tally + chapter-complete callout. Roster "You have 0" dupe count goes 13px bold red when 0, green when ≥ required.
  - #8 toast position moved from `bottom: 28px` to `top: 64px` so it lands in the natural reading focus zone.
  - **#6 portrait team picker** (`app/static/team-picker.js`) — full modal: portrait grid, side-mirrored selection slots, ATK/DEF/SUP filter chips, "🕘 Use last team" button, "💾 Save as preset" prompt, preset CRUD inline (Load / Rename / Overwrite / Delete). Replaces comma-separated ID input on Stages.
- **QoL catalog wired** (Phase 2.4 made functional):
  - `extra_team_presets` doubles cap 5→10
  - `auto_battle` echoes `auto_resolved` on /battles + skip-watch UI
  - `quick_summon` instant tab refresh
  - `roster_sort_advanced` adds Power/Level/Stars/Dupes/Name sort + faction filter chips
  - `cosmetic_frames` equippable via `POST /me/cosmetic-frame` + roster CSS overrides
- **Surfaces:** Currency banner header (always-visible totals + click-to-shop CTAs), 🦴 in-app overlay viewer (kills `target="_blank"` for internal pages), Resizable content panel prototype with localStorage-persisted width, Tutorial-hint tooltip overlay points at the relevant top-nav tab based on active `next_step`, Equipped-gear panel in hero detail sheet (6 slots, rarity-bordered), Variance pills (🔥/❄️) on roster grid cards, Daily tab consolidation (claimable summary banner + 2-up grid + Pull/Fight CTAs), Stage card team-power-vs-recommended comparison (✓/~/!).
- **Phase 3.1 attack-channel split** — `HeroTemplate.attack_kind` ('melee' | 'ranged') threaded through `build_unit` + log entries echo `channel`. Migration `f019b3d4ab7e`.
- **Phase 3.2 battle preview** — `POST /battles/preview` runs 5 sims, returns expected_outcome / win_probability / power_gap / notes; Stages tab "🔮 Preview" button + inline result panel.
- **Hardcore achievements teaser** — 8 long-tail goals locked-but-visible; `/achievements` response gets a `hardcore` block.
- **Achievement progress bars** — 11 catalog entries opt into a `progress` getter; UI renders inline fill bars.
- **Friends anti-spam** — per-day caps (50 friend requests, 300 DMs) layered on top of per-minute; DM body cap raised to 1500 chars.
- **Friends search UX** — debounced `GET /friends/search` returns up to 10 candidates annotated with relationship state (friend / pending / blocked). 6 tests.
- **Bug #7 closeout** — `toast.show` auto-detects "not enough X" patterns and renders a Shop CTA in the toast itself.
- **DragonBones Plan B greenlit + scaffolded:**
  - `/app/static/dragonbones-demo/` — Pixi 4.6 + DragonBones 5.7 runtime + Mecha 1004B sample. User confirmed visuals match the polish bar.
  - `app/static/battle-rigs/registry.json` — 37 units pre-mapped to placeholder mecha rig with head-texture paths.
  - `app/static/battle-pixi.html` — prototype replay viewer reading any battle id, walking the combat log → animations.
  - `docs/PLAN_B_INTEGRATION.md` — open architectural decisions (engine path, rig source, rig shape, asset pipeline).
  - `docs/BATTLE_RIG_EVENT_MAPPING.md` — production-rig contract (required animations, skin slots, event→animation route table).
- Suite at 568 passed, 4 skipped (RNG flakes, all pre-existing).

</details>

---

## 📎 How to use this file

- Tick `[x]` when something lands; delete fully-resolved lines rather than leaving graveyard checkmarks (except in the "Shipped" index).
- New work goes under **Backlog** in its section, and gets pulled into **Next up** when it's being planned.
- Keep **Where we're at** current — it's the top-of-file status at a glance.
- Assume this file is authoritative for what's still open.
