# Phase 2 — Human Test Checklist

**Status as of:** 2026-04-26 — code shipped, awaiting human verification.

This is the running tracker for hands-on testing of everything in Phase 2.
Tick `[x]` as items pass, `[!]` for found bugs (then add a row in "Bugs
found"), `[-]` for "skipped, won't test." Add new ideas to the "New test
ideas" section at the bottom and graduate them up to a real section once
they're worth running every release.

**Pair this with:** `tests/test_phase2_acceptance.py` — that test exercises
every PRD § 7 acceptance bullet in one flow. It's the automated bright
line; this doc is for everything you'd actually click on a real server.

## Legend

| Mark | Meaning |
|---|---|
| `[ ]` | Not yet tested |
| `[x]` | Verified working |
| `[!]` | Bug found — see "Bugs found" |
| `[-]` | Skipped / not applicable to this run |
| `[?]` | Inconclusive — couldn't reproduce or env-blocked |

## Session log

| Date | Tester | Notes |
|---|---|---|
| 2026-04-26 | ridler69 | Drive-by tab tour — context-switching with a server install fight. Logged 8 bugs (#1–#8 below). Story tab + Achievements + Notifications + Daily-claim + Guild tab all read fine on first impression. Battle visual + Arena explicitly deferred until Phase 3 combat depth lands. Lots of design-direction notes captured in "Phase 3 / future" section. |

---

## 0. The fast win — run the walkthrough script

If you can get any server up, this hits ~80% of the surface in one go.

```bash
HEROPROTO_MOCK_PAYMENTS_ENABLED=1 uv run uvicorn app.main:app &
uv run python -m scripts.client_walkthrough
```

Should print 17 sections + `CLIENT WALKTHROUGH PASSED`. First failure
points at the broken endpoint with full HTTP context.

- [ ] Walkthrough exits 0 with all 17 sections green

If this passes, items #2 / #3 / #6 / #8 / #9 / #10 / #12 below are also
covered automatically. Failure here means stop and triage before going
into the per-section tests.

---

## 1. EXILE faction default (Phase 2.5)

**What it is:** Every new account starts with `Faction.EXILE` ("not yet
aligned" in the bigger Corp story). Phase 3's level-50 fork will flip
this to RESISTANCE / CORP_GREED.

- [ ] Register a brand-new account → `GET /me` returns `faction: "EXILE"`
- [ ] /me also surfaces: `qol_unlocks: []`, `cosmetic_frames: []`,
      `hero_slot_cap >= 50`, `gear_slot_cap >= 200`,
      `account_level: 1`, `account_xp: 0`
- [ ] In the dashboard ⚙️ Account tab, faction shows "EXILE" somewhere
      visible (or accept that the UI hasn't surfaced it yet — flag if so)

---

## 2. Hero detail / next-upgrade preview (Phase 2.1)

**What it is:** `GET /heroes/{id}/preview` returns current vs after-stats
for level/star/special upgrade paths. The roster detail sheet now uses
this real preview instead of the old fake `power * 1.15` heuristic.

- [ ] Open Roster tab → click any hero → detail sheet opens
- [ ] On the Power line you see `+47 to 312 after star-up (0/1 dupes)` —
      *not* the old `+15% to ~XXX` format
- [ ] If the hero has a duplicate, the dupes count reads `≥1` and a `✓`
      shows on the same line
- [ ] API direct: `GET /heroes/{id}/preview` returns
      `{ current, level_up, star_up, special_up }` — each with
      `available`, `cost`, `delta`, `after`
- [ ] preview.current.power equals the same hero's power on /heroes/mine
      (no math drift between endpoints)

---

## 3. Stat variance on duplicate summons (Phase 2.2)

**What it is:** Pulling a hero you already own rolls a triangular ±10%
per-stat offset stored on `HeroInstance.variance_pct_json`. First copy
is always vanilla.

- [ ] Give yourself 1000+ shards (admin grant or DB poke)
- [ ] Run x10 summons until you land a duplicate
- [ ] Open the dupe in the roster detail sheet → "Roll variance: HP +3%
      · ATK -7% ..." line shows under Power, color-coded green if net-
      positive, red if net-negative
- [ ] First copy of any template still shows no variance line
- [ ] In combat: dupe's stats actually differ from the vanilla copy in
      battle simulation (verify via /battles result HP/ATK on the
      participants_json snapshot)

---

## 4. Story chapters + cutscenes (Phase 2.5)

**What it is:** 3 chapters (Onboarding / Middle Management / Executive
Floor) gated by account level. Cutscene text per stage. New /story API
+ /story/cutscene-seen endpoint.

> **2026-04-26 drive-by:** Story tab "looks ok at the moment" — chapters
> render, layout reads. Per-stage interactions and the question of
> whether stages should be renamed "challenges" pulled into Phase 3
> design notes below. API-level checks below still pending.

- [x] `GET /story` (or open 📖 Story tab) shows 3 chapters — visual ok
- [ ] Chapter 1 unlocked at account level 1
- [ ] Chapters 2/3 locked with "Unlocks at level 10 / 20" hint
- [ ] Chapter 1 lists 5 stages with cutscene `intro`/`outro` text
      preview
- [ ] `POST /story/cutscene-seen { chapter_code, stage_code, beat: "intro" }`
      returns 204
- [ ] Re-loading /story shows the seen cutscene flagged in
      story_state_json (DB row check)
- [ ] Bad chapter_code → 404; bad beat ("middle") → 400

---

## 5. Chapter-end reward grant (Phase 2.5 fix)

**What it is:** First-clearing the last stage of a chapter, when all
stages of that chapter are cleared, triggers a one-time bundle from
CHAPTER_END_REWARDS. Idempotent.

The hard way: actually clear all 5 stages.
The easy way: admin-poke `stages_cleared_json` then play the final stage.

- [ ] Reach 100% completion of Chapter 1 (Onboarding)
- [ ] Final stage clear triggers a `chapter_complete` notification (bell)
- [ ] /me shows +200 gems, +50 shards, +2 free_summon_credits delta
- [ ] /story now shows `chapters[0].completed: true`,
      `reward_claimed: true`
- [ ] Re-clearing the same final stage does not double-grant
- [ ] Chapter 2 (Middle Management) reward = +400 gems + 100 shards +
      3 access_cards + 3 credits — verify when you actually hit it

---

## 6. PoE2 QoL / cosmetic shop catalog (Phase 2.4)

**What it is:** New SKUs for QoL unlocks (auto_battle, extra_presets,
quick_summon, roster_sort_advanced), stackable slot packs (+25 hero,
+100 gear), 4 cosmetic frames + a frame bundle. Tone lock: never raw
power, only QoL or cosmetic.

> **2026-04-26 drive-by:** Shop tab is showing purchase history from a
> different account (`hello@zombiesub.com`). See bug #1 / #4 — same
> cross-account session leak. Tone-lock + SKU catalog itself still
> pending end-to-end verification once the leak is fixed.

- [!] Shop tab lists the new SKUs (or hit `GET /shop/products`) — tab
      renders but contaminated by prior account's purchase history
- [ ] Mock-buy `qol_auto_battle` → /me shows `qol_unlocks: ["auto_battle"]`
- [ ] Mock-buy `cosmetic_frame_neon` → /me shows
      `cosmetic_frames: ["frame_neon_cubicle"]`
- [ ] Mock-buy `slots_hero_pack` twice → `hero_slot_cap` jumps 50 → 75 → 100
- [ ] Mock-buy `slots_gear_pack` → `gear_slot_cap` jumps 200 → 300
- [ ] Mock-buy `cosmetic_frame_bundle` → all 4 frames appear
- [ ] One-time SKUs (auto_battle etc.) reject 2nd purchase with 409
- [ ] Stackable SKUs (slot packs) accept multiple purchases

---

## 7. Apple StoreKit + Google Play IAP (Phase 2.4)

**What it is:** `POST /shop/iap/{apple,google}` accepts a signed receipt
and grants the matching SKU. Sandbox shortcut: receipts prefixed
`fake-apple:` / `fake-google:` skip the real SDK and validate
structurally.

```bash
# Apple sandbox receipt:
POST /shop/iap/apple
{
  "sku": "qol_auto_battle",
  "receipt": "fake-apple:{\"productId\":\"qol_auto_battle\",\"transactionId\":\"test-123\"}"
}

# Google sandbox receipt:
POST /shop/iap/google
{
  "sku": "cosmetic_frame_neon",
  "receipt": "fake-google:{\"productId\":\"cosmetic_frame_neon\",\"orderId\":\"GPA.test-456\"}"
}
```

- [ ] Apple receipt → 201, `state: COMPLETED`, `processor: apple`
- [ ] Google receipt → 201, `state: COMPLETED`, `processor: google`
- [ ] Idempotency: re-POST same Apple receipt → returns same purchase id,
      no double grant
- [ ] SKU mismatch (body claims `qol_quick_summon`, receipt says
      `qol_auto_battle`) → 400 "sku mismatch"
- [ ] Empty receipt → 400 "empty receipt"
- [ ] Granted contents visible on /me immediately after the 201

---

## 8. Admin refund of IAP grants (Phase 2.4 fix)

**What it is:** Pre-fix, refunding an Apple QoL purchase left the unlock
owned (free-money bug). Now `apply_refund` reverses qol_unlocks /
cosmetic_frames / slot bumps.

- [ ] Buy `qol_auto_battle` via Apple sandbox receipt
- [ ] As admin: `POST /admin/purchases/{id}/refund { "reason": "..." }`
- [ ] Purchase `state: REFUNDED`
- [ ] /me shows `qol_unlocks: []` (auto_battle revoked)
- [ ] Buy `cosmetic_frame_neon` → refund → frame removed from /me
- [ ] Buy `slots_hero_pack` (cap 50 → 75) → refund → cap back to 50
- [ ] Buy `slots_hero_pack` 4× to push cap to 50+100=150 → refund one
      pack → cap goes to 125 (claws back 25, never floors below 50)
- [ ] Refund of `gems_small` (currency) still works as before
- [ ] Double-refund is rejected with 409

---

## 9. Myth-tier event banner (Phase 2.2 fix)

**What it is:** `LiveOpsKind.EVENT_BANNER` is a new kind. Players summon
Applecrumb / TBFAM via `POST /summon/event-banner` only during the
active window, with per-account pull cap.

### 9a — No active banner path

- [ ] `GET /summon/event-banner` returns `{ "active": false }`
- [ ] `POST /summon/event-banner` → 409 "no event banner is active"

### 9b — With an active banner

Insert a banner directly in the DB (or use `scripts/activate_event` if
you can shift the Mother's Day event into the present):

```sql
INSERT INTO liveops_events (kind, name, starts_at, ends_at, payload_json)
VALUES ('EVENT_BANNER', 'TestBanner',
  datetime('now', '-1 hour'),
  datetime('now', '+24 hours'),
  '{"hero_template_code":"applecrumb","shard_cost":8,"per_account_cap":3}');
```

- [ ] `GET /summon/event-banner` returns
      `{ active: true, hero_template_code: "applecrumb", pulls_used: 0,
         pulls_remaining: 3, shard_cost: 8, ends_at: "..." }`
- [ ] `POST /summon/event-banner` → 201, body has `rarity: "MYTH"`
- [ ] /me shards balance dropped by exactly 8
- [ ] Pull 3 times → 4th attempt 409 "cap reached"
- [ ] Insufficient shards (set shards=0) → 409 "not enough shards"
- [ ] Misconfigured banner (bad hero_template_code) → 500 "not seeded"
- [ ] Force `ends_at` into the past → next pull 409 (window expired)

---

## 10. Balance notebooks (Phase 2.6)

**What it is:** `analytics/*.ipynb` — three runnable Jupyter notebooks
producing committed PNG outputs.

- [ ] `uv sync --extra analytics` succeeds
- [ ] `uv run jupyter nbconvert --to notebook --execute --inplace analytics/gacha_ev.ipynb` exits 0
- [ ] Same for `combat_dps.ipynb` and `arena_convergence.ipynb`
- [ ] Output PNGs match the committed ones in spirit (rates table, hero
      DPS curve, rating convergence) — they regenerate cleanly even
      after balance edits to `app/gacha.py` / `app/combat.py`
- [ ] PRD acceptance: `analytics/output/gacha_ev_by_rarity.png` exists
      and shows the per-pull rarity distribution

---

## 11. Analytics events firing (Phase 2.3)

**What it is:** PostHog wrapper at `app/analytics.py` + 12 instrumented
events. Hard-disabled in test env; this section is for staging /
production verification.

- [ ] Set `HEROPROTO_POSTHOG_API_KEY=phc_...` + run
      `uv run python -m scripts.verify_analytics`
- [ ] All 12 sentinel events visible in PostHog Live Events within ~30s
- [ ] Run `client_walkthrough` against staging → events arrive with
      real `account_id` distinct_ids
- [ ] Import `scripts/posthog_dashboard.json` → 10 insights render
- [ ] First-purchase funnel (register → stage_clear[won=true] →
      purchase_complete) shows non-zero conversion after a walkthrough

---

## Cross-cutting concerns / regression watchlist

Things that have broken before or are easy to break in Phase 2:

- [ ] Old accounts (created before EXILE migration) read `faction: "EXILE"`
      via the `server_default` backfill — verify by checking a pre-2026-04-26
      account if any exist
- [ ] Variance round-trips through `participants_json` on a Battle row —
      replay must show the same stats the player saw in their roster
- [ ] Chapter-reward notification appears in the bell, not just the
      battle response payload
- [ ] /me response time hasn't regressed — Phase 2 added 4 new
      JSON-decode paths (qol, cosmetics, story state)
- [ ] Stripe Checkout flow still works (Phase 2 didn't touch it but the
      payment_adapters module restructure is adjacent)
- [ ] Migration chain runs clean from an empty DB (3 new alembic revs
      since Phase 2.3 close: faction, variance, qol+cosmetics)

---

## Bugs found

When something in this checklist fails, log it here. Format:
`#NN — short title — section that triggered it — repro / response`.

| # | Section | Issue | Repro | Status |
|---|---|---|---|---|
| 1 | Cross-cutting / auth | **Cross-account session leak.** Logged in as `kelsey.riddle@gmail.com` (new account) and saw 23 heroes + cards from a previous test account. Cleared after a few clicks. Suspect: localStorage `heroproto_jwt` not being cleared on logout / new register, or browser cache holding the previous /me + /heroes/mine response. Same symptom in §6 (shop showed `hello@zombiesub.com` purchases) and §arena (W1/L2 from prior account leaking in). | Register a new account in a tab that previously hosted another account session; check Roster + Shop tabs before refreshing. | **FIXED** — `heroSetAuthSession` / `heroClearAuthSession` helpers in base.html wipe per-account localStorage + clear `#content` on every login/register/logout/401. Wired into login.html, account.html (revoke-all), welcome.html, reset_password.html, static/index.html. |
| 2 | §0 / summon UX | **Summon recent-pulls feed doesn't refresh after a pull.** Have to take another action to see the new entry. Both x1 and x10 affected. | Open Summon tab, do a pull, look at "recent pulls" — old list. Click anything else, come back, new pulls appear. | **FIXED** — `summonFromTab` now inline-prepends the new pull cards to `#summon-recent-grid` so they appear instantly. Full tab re-fetch shortened from 1200ms → 600ms for pity/shards sync. |
| 3 | Sweep | **Sweep returns `422: [object Object]`.** Error message is unhelpful. Either the request shape changed or the toast layer is stringifying a Pydantic validation list wrong. | Open Stages → pick a cleared stage → Sweep → server returns 422; UI shows `[object Object]`. | **FIXED** — `SweepIn.team` now optional; backend falls back to the most recent winning team for that stage. Frontend re-renders SweepOut shape correctly (was reading non-existent fields). New `toast.formatErrorBody()` + `toast.fromError()` pretty-print Pydantic validation lists so future 422s read cleanly. 4 new tests in `test_sweep.py`. |
| 4 | §6 / shop | **Shop shows purchases from a different test account.** Same root as #1 (cross-account leak). Symptom localized to /shop/purchases/mine. | Already covered by #1 repro. | **FIXED** — same fix as #1. |
| 5 | Battle replay | **Post-mortem (battle result screen) shows no portrait.** Roster stats panel "You have 0" font is too small + needs a solid red color so empty state actually reads. No "create group" / preset-from-result option visible. | Win or lose any battle, look at the result panel. | **FIXED** — stages.html post-mortem now renders bust portraits + name + level for each hero that fought, plus reward currency tallies + chapter-reward callout. Roster detail sheet "You have 0" dupe count now 13px bold red when 0, green when ≥ required count. |
| 6 | Stages | **Team picker uses hero IDs, not portraits.** Nobody remembers ID numbers. Saved-team / "use last" flow is buried — Hero Roster team build is hard to find and there's no save/edit/rename/delete UI for presets. | Stages tab → pick a stage → team field is a comma-separated ID input. | OPEN — UI: portrait-based picker + preset CRUD surface (deferred — bigger UX overhaul, queued with the Phase 3 design notes) |
| 7 | Daily / shop | **Lots of dead space on Daily tab.** Could host a banner bar with currency totals + "buy more gems" tease. When user is short on a currency mid-purchase, surface a "go to shop" CTA at the failure point instead of a generic 409. | Open Daily tab; try to summon with 0 shards. | OPEN — UX consolidation (deferred — needs design pass) |
| 8 | Cross-cutting / errors | **Error messages render at the bottom of the screen.** User clicking near the top doesn't see them. Should pop near the click target (toast-relative or inline-by-button). | Trigger any 4xx (e.g. summon with 0 shards). | **FIXED** — toast stack repositioned from `bottom: 28px` (column-reverse) to `top: 64px` (column) so toasts land in the natural reading focus zone. |

---

## New test ideas (graduate to sections above when worth it)

- [ ] Variance under +/- floats edge cases — what if `participants_json`
      JSON-decode fails mid-battle? Sim should fall back gracefully.
- [ ] EVENT_BANNER + variance interaction — pulling Applecrumb twice in
      one event should give the second copy variance.
- [ ] Chapter reward firing across multiple chapters in one battle
      session (theoretically impossible due to ordering but worth a
      poke if you ever batch-clear).
- [ ] QoL unlock in `/me` doesn't actually gate any UI yet — the
      `auto_battle` flag is owned but where does it actually toggle a
      different flow? (Ship Phase 3 acks this; Phase 2 just owns the
      catalog.)
- [ ] Cosmetic frames don't render on hero cards yet — UI side-quest.
- [ ] Per-event-banner pull *history* — should pulls show up in
      gacha_records with a flag distinguishing event banner from
      standard? Currently they're commingled.
- [ ] Refund analytics — when a Purchase flips REFUNDED, do we fire a
      `purchase_refund` PostHog event? Probably should.

---

## Phase 3 / future design notes (raw from playtests)

Captured 2026-04-26 during the drive-by tab tour. Not Phase 2 acceptance
work — these are direction notes for combat depth / UX-overhaul phases.
Listed in roughly the order they were observed.

### Tutorial UX
- Needs popup hints / tooltip overlays guiding "click here next."
- Skip-tutorial button — express path for returning users.
- Idea: branch tutorial into "Express" vs "First-Timer" — same end
  reward, different pacing. Reward should be generous-but-not-crazy.
- Emphasize the prize at the end so the carrot is visible mid-tutorial.

### Summon tab
- Recent-pulls feed is stale until next action (logged as bug #2).
- Sub-menu / tabs for special summons. More banners = more reasons to
  spend currency.
- Card images in recent-pulls should be clickable → opens that hero's
  detail sheet.

### Battle viewer / animation pipeline
- **Battle visual hasn't changed.** Should be next priority — players
  spend most of their time on the battle screen.
- Replace static portrait roster art with animated actors (Moho,
  Adobe 2025 full suite is what's available).
- Need a setup script for the animation export pipeline.

### Stages tab → "Challenges"
- Rename stages → challenges per playtest gut feel.
- Team picker should use portraits, not numeric IDs (bug #6).
- Map-based stage navigation: place stage nodes on a world map,
  per-region or geo-randomized to player's login country. Hover →
  shows the local stage menu (1-1, 1-2, ...). Next stage highlighted,
  later stages greyed with minimal detail.
- Per-stage backgrounds + light story interaction so stages feel like
  progress, not "a screen of boxes."

### Hero roster / team build
- "Very obscure to find." Surface the team builder as a top-nav action,
  not buried in roster.
- Save / edit / rename / delete UI for team presets (bug #6).
- Replace placeholder roster art with the cluster-of-fuckery card art
  pipeline output.

### Synergy rework
- Cap at max 2 active synergies per team. Rule of thumb: a team with
  2 yellow + 2 blue + 1 purple lights up the 2★ tier of yellow + blue,
  purple gets nothing.
- Tier the synergy ladder 2★ → 5★ to give more creative team combos
  meaningful reward.
- More gear slots / things to gear into for variety.

### Daily / shop UX
- Lots of dead space on Daily tab (bug #7). Consolidate.
- Banner bar with character art + currency totals + "buy more" CTA.
- When a purchase fails for insufficient currency, popup CTA → shop
  route, not a generic 409.
- Confirmed working: `daily_bonus_claim` payload looks correct
  (logged: `{"id":7,"day_key":"2026-04-26","kind":"SUMMON_HEROES",
  "status":"CLAIMED","goal":10,"progress":10,"reward_gems":20,
  "reward_coins":500,"reward_shards":2}`)

### Friends tab
- Anti-spam / RMT seller / racism guards needed before launch.
- Friend-request rate limit per day, message length limits, etc.
  (Some buckets already shipped — verify coverage during Phase 3.)

### Achievements
- Looks good. Add a "hardcore achievements" teaser somewhere visible
  to seed long-term engagement.

### Arena overhaul (waiting on combat depth)
- Defer until battle layer is figured out. Will be the highest-pressure
  competitive surface.
- Payout schedule: avoid one-shot 24h payouts — staggers favor a single
  timezone. Need to think through global fairness so the market doesn't
  saturate / get fucked.
- Bug #1 may be the source of the W1/L2 record showing on the new
  account — investigate alongside the cross-account leak.

### Guild tab
- Fine for now. Future: guild perks. POE2 had a great cosmetic system
  with a separate currency — worth modeling.

### Notifications
- Bell looks fine. Backburner.

### Tech / framework asks
- **Resizeable windows per tab** — feasibility ask. How much code? Just
  ballpark whether it's a CSS-grid swap or a full layout-engine
  rewrite, then decide.
- Modal/popup close affordance — too many tabs open new windows; need
  a consistent dismiss UX.
- Backgrounds + visual detail without performance regressions —
  need to figure out the budget before art lands.

---

## Setup gotchas / troubleshooting

Stuff that has eaten time during install:

- **Stale bytecode**: if migrations re-run with old schema, delete
  `app/__pycache__/` + `tests/__pycache__/`.
- **Mock payments off**: shop endpoints look broken — set
  `HEROPROTO_MOCK_PAYMENTS_ENABLED=1` in env *before* starting uvicorn.
- **No starter team on register**: `_grant_starter_team` skips silently
  if no COMMON heroes are seeded — re-run `uv run python -m app.seed`.
- **EXILE column missing on existing DB**: pull the latest then run
  `uv run alembic upgrade head` to add `accounts.faction`.
- **Variance shows nothing**: only fires on dupes — first copy of every
  template stays vanilla forever. Need 2+ of the same template.
- **Chapter reward not firing**: only on `first_clear` of the *last*
  stage when *all* chapter stages are cleared. Re-clearing nothing.
- **Event banner endpoint 409 even with active row**: check the
  `starts_at <= now < ends_at` window — DB may have your row in UTC
  but the server clock differs. Set both clocks to UTC.
- **Notebooks fail to execute**: `uv sync --extra analytics` is the
  step you forgot. Jupyter is opt-in.

---

## Sign-off

When every section above is `[x]` (or has a tracked bug entry):

- [ ] Tag the commit `phase-2-verified`
- [ ] Update `docs/PRD.md § 7` status from "code shipped" to "verified shipped"
- [ ] File the bugs as Phase 3 polish issues
- [ ] Move on to Phase 3 — combat depth (PRD § 8)

> Drive-by playtest notes from 2026-04-26 have been folded into the
> "Bugs found" table (#1–#8) and the "Phase 3 / future design notes"
> section above. Raw notes archived in commit history if needed.













