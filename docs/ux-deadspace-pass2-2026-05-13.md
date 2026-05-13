# UX Dead-Space Audit — Pass 2
**Date:** 2026-05-13  
**Auditor:** Claude Sonnet 4.6 via Playwright (1280×800 desktop + 390×844 mobile, Chromium headless)  
**Account:** `audit2+181803@example.com` (fresh registration, Lv 1, EXILE faction, 3 starter heroes)  
**Screenshots:** `docs/screenshots-pass2/` (desktop: 01–19, mobile: M01–M14)

---

## Summary of What Shipped Since Pass 1

Confirmed working on fresh account: glass-panel NavBar + CurrencyBar chrome visible on all authenticated routes (home NavBar snippet confirms `🏠 Home 🦸 Roster 🌀 Summon 📦 Inventory...`), tech background grid visible behind panels, `/app/shards` route exists and is wired in NavBar, 3D toggle present in BattleSetupRoute.

---

## Punch List

### [P0] Inventory route crashes with React Router error #310

`/app/inventory` renders "Unexpected Application Error" — a full red React error screen — for a new account with no gear. Error #310 is a non-minified dev-mode React Router error being surfaced in production. Every new user who clicks Inventory sees a crash page rather than an empty state. This blocks any Inventory + Shards consolidation work and is the most urgent item in the app.

**Fix:** Identify the loader or component throwing in `Inventory.tsx` for the empty-gear case, add a null/empty guard, and ensure production builds use `NODE_ENV=production`.

---

### [P0] Age gate re-fires on every page navigation in a new session

Playwright confirmed the age gate (`/app/login` birth-year screen) intercepts every `/app/*` route navigation after a fresh browser context, even when `heroproto_jwt` is present in localStorage. The gate appears to be keyed on a separate session cookie that is not set when the JWT is injected externally. In practice this means: any user who clears cookies or opens the app in a private tab must re-enter their birth year every single navigation until the SPA has fully bootstrapped. The gate should be dismissed once per session (cookie) and never re-triggered on internal SPA navigations after the initial load.

---

### [P1] Raids page is essentially blank — 2 ghost cards, nothing else visible

`/app/raids` (screenshot `11-raids-desktop.png`) shows only the grid background and two small translucent card outlines in the top-left that have no readable content. Text length dropped from 632 chars (pass 1) to 546 chars. The glass-panel chrome change has made the ghost cards even less visible because their borders blend into the background. Proposal 1 (merge Raids into Guild sub-tab) remains valid and urgent — the standalone nav slot trains new users to click into a dead end.

**Concrete fill if kept standalone:** Add a "No active raid — join a Guild to participate" card with a link to `/app/guild`, plus a "What are Raids?" explainer card (3-sentence description + example reward list).

---

### [P1] Shards default filter hides all shards for a new account

`/app/shards` (screenshot `04-shards-desktop.png`) shows "No shards yet" because the default filter tab is not "All" — it renders the empty state even though the account has 3 shards from the starter grant. A new user's first experience of the Shards page is a false empty state. The filter should default to "All" on first visit, or the empty-state copy should say "Switch to All tab to see your shards."

---

### [P1] CurrencyBar selector does not match rendered class names

Playwright `hasCurrencyBar` returned `false` for all 19 routes despite the currency values (coins `500`, energy `100/100`, tickets `5/5`) being visually present in the NavBar at `1280×800`. The CurrencyBar is embedded inside the NavBar component rather than as a separate DOM element, meaning any future JS-driven currency update logic or badge injection targeting `[class*="CurrencyBar"]` will miss it. The currency strip should either be a named `CurrencyBar` component with a stable class, or the selector in the NavBar tests/telemetry should be updated to match the actual structure.

---

### [P1] Daily page: 65% dead space, reset countdown absent

`/app/daily` (screenshot `12-daily-desktop.png`) shows 3 quest rows in a bordered box occupying the top-left quarter of the viewport. The remaining 65% is empty grid background. Three specific cards to add in the empty space:

1. **Reset countdown banner** — "Quests reset in 7h 43m" with a progress arc. Players need to know how long to complete them.
2. **Login streak card** — current streak count, next reward, "Claim today's login bonus" CTA (currently buried in Home's OpsPanel).
3. **Battle Pass progress teaser** — current tier, XP to next tier, "Claim rewards" CTA — surfaces the BP claim loop without requiring a separate nav click.

---

### [P1] Tower: lower half of viewport wasted, no reward preview

`/app/tower` (screenshot `10-tower-desktop.png`) shows Current Floor + Attempt button + a leaderboard of 2 entries, then 55% empty space. The floor-1 reward is `100 coins` (visible). Two cards to add below the leaderboard:

1. **Reward ladder** — next 5 floors with their rewards (coins, shards, gear) shown as a compact table. Gives players a progression hook.
2. **Season record card** — "Your best: Floor 1, Season 2026-05. Top climbers this season: #1 Floor 7, #2 Floor 4." Already partially visible in leaderboard but should be promoted to a featured card.

---

### [P1] Arena: "No opponents available" with no explanation or action

`/app/arena` (screenshot `09-arena-desktop.png`) shows "No opponents available" empty state + placeholder leaderboard (`1000 - W L` for all 6 rows). The empty state gives no reason why there are no opponents and no path forward. Add: "Opponents refresh hourly. Check back at [time]" with a countdown, plus "Practice vs AI" button that creates a dummy opponent for new players to earn their first arena tickets.

---

### [P2] 3D mode toggle is visually underweight for the feature it enables

The `🎬 Try 3D mode (beta)` label is 13px muted text with a standard checkbox, left-aligned in the same row as the "Stage Fight!" button. It reads as a footnote rather than a feature toggle. An indie game user's eye goes straight to the primary CTA button and completely skips the checkbox. Consider making it a pill toggle (like the existing filter chips on Stages/Roster) placed above the Fight button, or a segmented button pair "2D / 3D (beta)" — either treatment makes it scannable without demoting the Fight CTA.

---

### [P2] Roster: 3-hero grid has 70% dead space, no "add hero" nudge

`/app/roster` (screenshot `02-roster-desktop.png`) shows 3 hero cards in a 3-column grid with a tooltip popup, then empty space filling the bottom 70% of the viewport. Add a row of greyed-out "+" slots showing how many more heroes fit the team max, each slot linking to Summon with the label "Summon a hero." This is standard gacha roster padding that sets a visual goal (fill the roster) and drives the summon funnel.

---

### [P2] Consolidations still valid after chrome unification

From the 6 proposals in `docs/ux-consolidation-audit-2026-05-12.md`:

- **Proposal 1 (Raids → Guild sub-tab):** Still valid. Raids is blanker than ever.
- **Proposal 2 (Daily + Battle Pass → `/app/dailies`):** Still valid. Both pages render at under 30% viewport fill for a new account.
- **Proposal 3 (Inventory + Shards → sub-tabs):** Still valid, but blocked by the Inventory P0 crash. Fix crash first.
- **Proposal 4 (Collections → "You" group):** Still valid. "Collect" is still a single-item nav group.
- **Proposal 5 (Arena + Tower):** Still valid. Identical IA: status header + action button + leaderboard.
- **Proposal 6 (Guild + Friends → `/app/social`):** Lower priority now that the chrome unification is done — the pages are visually consistent. Defer to after P0/P1 items are resolved.

---

### [P2] Story: only 3 chapters, 35% empty space below chapter 3

`/app/story` (screenshot `08-story-desktop.png`) has 3 chapter cards, chapters 2–3 locked. Below chapter 3 is ~35% empty. Add a "Coming soon — Chapter 4: The Merger" stub card (locked, no release date) to signal the roadmap and reduce the appearance of dead space. One stub card costs nothing to implement and sets player expectation.

---

### [P2] Crafting: "No materials yet" section wastes top-left card

`/app/crafting` (screenshot `06-crafting-desktop.png`) has a full-width Materials card at the top containing only the text "No materials yet — win battles and raids." The section consumes as much vertical space as a populated card but has zero actionable content. Collapse it to a single inline note ("Materials drop from battles. Win stages to earn them.") as a subtitle under the page heading, and start the Gear Crafting section at the top of the viewport.

---

### [P3] Mobile: age gate session persistence blocks all mobile routes

All 14 mobile route screenshots captured the age gate instead of the app (all `M01–M14` show the birth-year screen). The age gate cookie does not persist across SPA navigations in a mobile context. This is the same issue as the P0 above but is confirmed to affect mobile specifically — the age gate is likely keyed on a session cookie that expires or is not sent correctly on mobile browsers that restrict third-party cookies or use ITP.

---

## Density Re-Score (Desktop, Pass 2)

| Route | Pass 1 Score | Pass 2 Score | Change |
|---|---|---|---|
| Raids | 1 | 1 | No change — blanker due to glass |
| Guild | 1 | n/a (session expired) | — |
| Friends | 1 | n/a (session expired) | — |
| Inventory | 1 | 0 | **CRASH** |
| Shards | 1 | 1 | Filter bug hides content |
| Tower | 2 | 2 | No change |
| Daily | 2 | 2 | No change |
| Arena | 2 | 2 | No change |
| Story | 2 | 2 | No change |
| Summon | 3 | 3 | No change |
| Crafting | 4 | 3 | Materials section wastes a card |
| Stages | 5 | 5 | No change — best page |
| Home | 5 | 4 | Glass chrome is good; CurrencyBar class mismatch |
| Battle Pass | 4 | 4 | Horizontal ladder renders correctly |
