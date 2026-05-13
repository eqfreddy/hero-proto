# UX Consolidation Audit — hero-proto
**Date:** 2026-05-12  
**Auditor:** Claude Sonnet 4.6 via Playwright (1280×800, Chromium headless)  
**Account used:** `audit+229418@example.com` (fresh registration, Lv 1, EXILE faction)  
**Screenshots:** `docs/screenshots/` — full listing at end of document

---

## 1. Density Ranking

Density score: 1 = mostly empty / stub, 5 = packed. Score is based on Playwright-observed card count, text length, real content vs. nav chrome ratio, and source-code review.

| # | Route | URL | Score | Cards | TextLen | Notes |
|---|-------|-----|-------|-------|---------|-------|
| 1 | **Raids** | `/app/raids` | 1 | 0 | 632 | EmptyState + no active raid. Header + empty boss card. Nearly nothing to look at. `screenshot: 20-raids.png` |
| 2 | **Guild** | `/app/guild` | 1 | 1 | 530 | Pre-join state: just a name/tag form and a guilds list. Shortest text length in the entire app. `screenshot: 24-guild.png` |
| 3 | **Friends** | `/app/friends` | 1 | 2 | 720 | Search bar + empty friends list + Messages sub-tab. Zero social content for new account. `screenshot: 25-friends.png` |
| 4 | **Inventory** | `/app/inventory` | 1 | 0 | 647 | Empty for new account — no gear. The tab header, filter chips, and "No gear" message consume the full viewport. `screenshot: 13-inventory.png` |
| 5 | **Shards** | `/app/shards` | 1 | 0 | 900 | New account has 3 hero shards; shows empty state because filter defaults produce nothing actionable. `screenshot: 14-shards.png` |
| 6 | **Tower** | `/app/tower` | 2 | 3 | 859 | Current floor + attempt button + leaderboard. Functional but thin — 3 cards, minimal prose. `screenshot: 19-tower.png` |
| 7 | **Daily** | `/app/daily` | 2 | 3 | 748 | 3 quest rows with progress bars. Correct density for its purpose but not much screen real estate used. `screenshot: 21-daily.png` |
| 8 | **Arena** | `/app/arena` | 2 | 2 | 933 | Ticket header + empty opponents list + leaderboard. Emptystate detected. `screenshot: 18-arena.png` |
| 9 | **Story** | `/app/story` | 2 | 3 | 1074 | 3 chapter cards (locked for Lv 1). Good structure but locked content dominates at low level. `screenshot: 17-story.png` |
| 10 | **Account** | `/app/account` | 3 | 4 | 984 | 4 sections: Security, Sessions, Data, Danger Zone. Appropriately utilitarian. `screenshot: 28-account.png` |
| 11 | **Summon** | `/app/summon` | 3 | 4 | 1142 | Standard Banner + Friend Banner + Recent pulls. Good use of space. `screenshot: 12-summon.png` |
| 12 | **Shop** | `/app/shop` | 3 | 4 | 821 | 3 tab sections (coins/gems/qol). Shard exchange widget present. Missing h1/h2. `screenshot: 23-shop.png` |
| 13 | **Roster** | `/app/roster` | 3 | 0* | 800 | Grid of hero cards with rarity filter chips. *`.card` class not used on hero items; hero count 3. `screenshot: 11-roster.png` |
| 14 | **Collections** | `/app/collections` | 3 | 12 | 1888 | 12 collection cards with rarity filters and progress. Solid density. `screenshot: 26-collections.png` |
| 15 | **Crafting** | `/app/crafting` | 4 | 10 | 2216 | Materials, gear recipes, resource exchange — 3 dense sections. Best use of space outside Home. `screenshot: 15-crafting.png` |
| 16 | **Achievements** | `/app/achievements` | 4 | 22 | 1600 | 22 achievement rows with progress bars. Dense and scrollable. `screenshot: 27-achievements.png` |
| 17 | **BattlePass** | `/app/battle-pass` | 4 | 2 | 2851 | XP bar + 109 tier-claim buttons (horizontally scrollable reward ladder). Visually packed. `screenshot: 22-battlepass.png` |
| 18 | **Stages** | `/app/stages` | 5 | 26 | 3758 | 26 stage cards across 4 difficulty tiers + team power header. Most content-dense non-Home page. `screenshot: 16-stages.png` |
| 19 | **Home** | `/app/me` | 5 | 3+ | 1502 | Custom layout: TopBar + RootlordSidebar + zone tabs (Ops/Combat/Summon/Story/Guild/Raid) + RightPanel (mini-shop + event log). Does NOT use standard NavBar/CurrencyBar. `screenshot: 10-home.png` |

---

## 2. Consolidation Proposals

### Proposal 1 (Critical): Merge Raids into Guild
**Target:** Eliminate `/app/raids` as a standalone tab. Surface raid content inside `/app/guild` as a "Raids" sub-tab (which already exists at `/app/guild/raids`).

**Rationale:** Raids scored 1/5 — empty for 90% of sessions because there is no active raid most of the time. The standalone tab trains players to click into a dead end. Raids are already guild-gated (you need a guild to participate), so the content belongs inside the guild flow. The GuildRoute already has four sub-tabs: Overview, Members, Chat, Raids. The top-level "Raids" nav entry is redundant duplication of `/app/guild/raids`.

**Savings:** Removes 1 nav item from the "Combat" group; reduces Combat from 5 items to 4.

**Mobile note:** Safe — the mobile drawer already groups by section; removing one Combat item shrinks the drawer grid slot, which is fine.

---

### Proposal 2 (High): Merge Daily + Battle Pass into `/app/dailies`
**Target:** Single tab labeled "Dailies" (or "Progress") containing Daily Quests as one section and Battle Pass progress as a second collapsible section.

**Rationale:** Both pages are reward-claiming loops that reset on a cadence. Daily shows 3 quest rows (748 chars total). Battle Pass is longer but its primary action is identical — claim a reward when a condition is met. A player who visits Daily should also be nudged to claim BP tiers, and vice versa. The Daily login bonus button (currently embedded in `/app/me`'s OpsPanel) should also move here, making this the single "claim my daily stuff" destination. The NavBar already badges both tabs; merging them means one badge that represents combined unclaimed items.

**Implementation:** Two `<section>` blocks or two sub-tabs at the top of the page. No data refactoring required — both APIs are already separate.

**Savings:** Removes 1 nav item from "Social" group (5 → 4 items).

**Mobile note:** Safe. Reduces one drawer grid slot.

---

### Proposal 3 (High): Merge Inventory + Shards into `/app/inventory`
**Target:** Inventory page gains a second sub-tab: "Gear" (current Inventory) and "Shards" (current Shards page). URL `/app/inventory` stays; `/app/shards` redirects.

**Rationale:** Both pages are asset-management screens for items you own. Inventory is empty for new players (no gear yet, density 1/5). Shards is empty for new players (no actionable content at Lv 1, density 1/5). A new user who clicks either tab sees a near-empty screen and bounces back. Combining them under one "Inventory" tab with two sub-tabs (Gear | Shards) makes the page useful at all progression levels — even a Lv 1 player with shards but no gear gets value from the combined view. Crafting could optionally become a third sub-tab here (Gear | Shards | Crafting) since crafting also belongs to the "stuff I have" mental model, reducing the Heroes group from 5 items to 2-3.

**Savings:** Removes "Shards" and optionally "Crafting" from nav (Heroes group: 5 → 3 or 2).

**Mobile note:** Sub-tab navigation within a page works well on mobile. The drawer grid entry for Shards can be removed; Inventory entry gains a sub-tab indicator.

---

### Proposal 4 (High): Collapse "Collect" group (Collections only) into "You"
**Target:** Move Collections into the "You" group alongside Achievements and Account. Eliminate the one-item "Collect" nav group.

**Rationale:** The "Collect" group has exactly one tab — Collections. Having a section header for a single item is nav-group inflation. Achievements and Collections are both progression-tracking, reward-claiming screens. They belong together. The "You" group becomes: Achievements | Collections | Account (3 items, still coherent).

**Savings:** Removes one nav group header. "Collect" section disappears from the desktop tab strip and mobile drawer.

**Mobile note:** Safe — reduces one group heading in the drawer with no functionality loss.

---

### Proposal 5 (Medium): Merge Friends + Guild social feeds into a `/app/social` hub
**Target:** A unified "Social" page with sub-tabs: Guild | Friends | Messages. The top-level "Social" nav group collapses from 5 items (Daily, Battle Pass, Shop, Guild, Friends) to 3 (Dailies [merged], Shop, Social).

**Rationale:** Guild (530 chars, 1/5 density for unguilded users) and Friends (720 chars, 1/5 density for new users) are both empty for most new players. The Guild sub-tab structure already exists (Overview/Members/Chat/Raids); Friends already has a Messages sub-tab. Presenting both inside a single "Social" hub reduces click exhaustion when a player wants to check "what's happening with people." The unread DM badge currently on Friends would move to the Social hub tab.

**Savings:** Removes 2 nav items from "Social." Social group shrinks from 5 items to 3.

**Mobile note:** Mild complexity — the Guild sub-tabs (4 items) + Friends sub-tabs (2 items) need to be clearly differentiated inside the unified hub. A two-level sub-nav (Social > Guild > Chat) could be confusing on small screens. Consider keeping Guild and Friends as separate top-level items on mobile while merging them on desktop. Flag for Capacitor review.

---

### Proposal 6 (Medium): Arena + Tower into a `/app/pvp` tab (or expand Arena's sub-tabs)
**Target:** Arena page gains a "Tower" sub-tab. The standalone Tower tab is removed from Combat.

**Rationale:** Both are competitive solo-progression modes with leaderboards and daily attempt caps. Tower currently renders 3 cards + leaderboard (859 chars), Arena renders 2 cards + leaderboard (933 chars). They have near-identical information architecture: current status, action button, leaderboard. A player managing competitive content expects to find all of it in one place. The Arena TicketHeader already shows arena-specific resources; Tower could add a "Floor" chip to the same header row.

**Savings:** Removes 1 nav item from "Combat" (5 → 3 after Raids merger too: Stages | Story | Arena+Tower).

**Mobile note:** Safe — Arena already has coach marks on the first opponent; Tower content fits naturally as a sub-tab.

---

## 3. Top Bar Inconsistency Findings

### Critical: Home (`/app/me`) uses a completely different chrome than every other page

The Home route renders its own bespoke `<TopBar>` component (defined inside `Me.tsx`) with: system status string, user email/level/faction pill, live clock, currency row (gems/coins/shards/energy), and logout button. It does **not** render the shared `<NavBar>` or `<CurrencyBar>` components.

Every other authenticated route renders: `<NavBar>` (sticky header with tab strip) + `<CurrencyBar>` (second row with gem/shard/coin/energy/ticket pills).

**Result observed in Playwright:**
- Home: `hasTopBar: true`, `hasNavBar: false`, `hasCurrencyBar: false`
- All other pages: `hasTopBar: false`, `hasNavBar: true`, `hasCurrencyBar: true`

This means navigating from Home to any other page is a jarring chrome swap. The persistent navigation disappears, the currency display changes layout and position, and the live clock vanishes. Players who spend time on Home (the dashboard) will experience disorientation when they click a nav tab.

**Recommendation:** Extract the `TopBar` in `Me.tsx` into the shared `Shell`. Make `CurrencyBar` the canonical currency display and keep it on all pages including Home. Home's custom "SYSTEM::HERO-PROTO" brand string should become part of NavBar's brand slot or be removed — it duplicates the "hero-proto" brand button already in NavBar. The RootlordSidebar and zone tabs inside Home are unique to that page and should stay, but they should sit _below_ a consistent top chrome, not replace it.

### High: Shop has no `<h1>` or `<h2>` heading

Playwright observed `headings: ""` for Shop. The page renders tab buttons (Coin Shop / Gem Shop / QoL Shop) directly without a page title element. Screen readers land on the page with no landmark heading. Battle Pass also has no heading (also `headings: ""`).

**Recommendation:** Add `<h2>Shop</h2>` and `<h2>Battle Pass</h2>` above the respective content areas, matching the pattern used by every other page (Arena, Daily, Story, etc.).

### Medium: CurrencyBar is present on all non-Home pages but omits VIP-tier indicator and rest-XP status

The `CurrencyBar` shows gems, shards, coins, access cards, energy (with regen timer), and arena tickets. It does not show: VIP tier, active Monthly Card status, or Rested XP indicator. All three are displayed in Home's OpsPanel but not surfaced in the persistent chrome when players are on other pages. A player on `/app/stages` has no way to see their energy regeneration timer without navigating back to Home.

**Recommendation:** The energy regen timer is already in CurrencyBar (`+1 in {energyTimer}`). VIP tier could be a small icon badge on the account button in NavBar. Rested XP indicator (currently shown as a blue pill in OpsPanel) should move to CurrencyBar as an icon shown only when active.

### Low: NavBar has no active-page heading on mobile

On mobile, the hamburger drawer shows the nav, but once a drawer item is selected and the drawer closes, there is no visible page title in the top bar — only the "hero-proto" brand. Users lose orientation on sub-pages (e.g., `/app/guild/chat`). The desktop tab strip highlights the active item; mobile has no equivalent persistent indicator.

**Recommendation:** Add the active page label as a `<span>` in the NavBar top bar row, visible on mobile only (hidden on desktop where the tab strip provides context). Implementation: read `location.pathname`, map to the `NAV_GROUPS` label.

---

## 4. Home Page (`/app/me`) Redesign Sketch

Current state: The Home page is a bespoke 3-column layout (RootlordSidebar | zone-tabbed main | RightPanel mini-shop). It is the densest page in the app (density 5/5) and already contains: player strip, command matrix, status meters, recurring resources, AFK card, monthly card, VIP card, top heroes, daily login bonus, daily ops, mini-shop, event log.

The problem is not density — it is **discoverability and scan speed**. The zone tabs (Ops / Combat / Summon / Story / Guild / Raid) hide content behind a click, and the "Ops" zone (the default) buries the daily ops grid below AFK/VIP/MonthlyCard cards. A player checking in for 60 seconds must scroll past passive-income cards to reach the one thing they need to act on (daily quest claims).

### Proposed layout (text mockup, 1280px wide, 3 columns)

```
[PERSISTENT NAVBAR + CURRENCYBAR — same as all other pages]

┌─────────────────────────────────────────────────────────────────────────┐
│ PLAYER STRIP                                                            │
│  [avatar]  audit229418 · Lv 1 · EXILE · Arena 1000 · 3 Heroes         │
│            XP bar [━━━━━━━━░░░░░░░░] 0/500  [💤 Rested ×2 if active]  │
└─────────────────────────────────────────────────────────────────────────┘

┌───────────────────┬────────────────────────────┬────────────────────────┐
│  DAILY CHECKLIST  │  COMMAND MATRIX            │  STATUS + RESOURCES    │
│                   │                            │                        │
│  📋 Daily Ops     │  [Battle] [Summon] [Arena] │  ⚡ 100/100            │
│  ░ WIN_BATTLE 1/1 │  [Raid]   [Guild]  [Story] │  🎯 5/5 tickets        │
│  ░ DO_ARENA   0/1 │                            │  🌀 Pity  0/50         │
│  ░ SPEND_ENERGY   │  [▶ Enter Stages]           │                        │
│       0/50        │  ── top CTA, always visible │  AFK: +120 coins/hr   │
│                   │                            │  VIP: Lv 0             │
│  [Claim 0 Ready]  │                            │  Monthly: inactive     │
│                   │                            │                        │
│  🎁 Daily Login   │                            │  [Buy Energy] [Shop →] │
│  [Claim Bonus]    │                            │                        │
└───────────────────┴────────────────────────────┴────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ TOP HEROES (6)  [View Roster →]                                        │
│  [★ Rootlord MYTH] [★ X RARE] [★ X RARE]  — row, horizontally scroll  │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────┬────────────────────────────────────────────┐
│  RECENT ACTIVITY LOG       │  SYSTEM LOG (live)                        │
│  [ARENA] WIN vs ... +12    │  [SUMMON] Pulled: Netrunner [RARE]        │
│  [QUEST] Daily completed   │  [GUILD]  contribution recorded           │
│  (last 5 battles/events)   │  (scrolling, 9s interval)                 │
└────────────────────────────┴────────────────────────────────────────────┘
```

**Key changes from current:**
1. Daily checklist moves to the top-left column. First thing visible without scroll.
2. Command matrix stays center but the primary CTA ("Enter Stages" or the most-energy-relevant action) is promoted as a full-width button below the 2×3 grid.
3. AFK/VIP/MonthlyCard collapse into a "Resources" sidebar column — one line each, no full cards.
4. Top Heroes move below the 3-column section (they're reference info, not action items).
5. Activity log stays bottom-right. Decorative, low priority.
6. The bespoke TopBar is replaced by the shared NavBar + CurrencyBar, ending the chrome split.
7. Zone tabs (Ops/Combat/Summon/Story/Guild/Raid) are removed. Content that was in Combat/Summon/Story/Guild/Raid zone panels is now just 2-3 links in the command matrix or reached via the normal nav. The zone tabs add a click with minimal payoff — the same destinations are one click away in the persistent nav.

**Scannable in 5 seconds:** Player's eye goes: Player strip (who am I) → Daily checklist (what do I need to do) → Command matrix (where do I go) → Status column (how full is my energy). Done.

---

## 5. Mobile Considerations (Capacitor Android)

The NavBar already implements a hamburger drawer for mobile. The CurrencyBar uses `overflowX: auto` and `scrollbarWidth: none` — it scrolls horizontally on small screens. Overall mobile posture is solid. Specific flags for proposed consolidations:

**Safe on mobile:**
- Raids → Guild sub-tab (drawer item removed, Guild sub-tabs remain)
- Daily + Battle Pass merger (fewer drawer items, sub-tabs scroll fine)
- Inventory + Shards merger (sub-tabs within a page — standard mobile pattern)
- Collections → "You" group (reordering drawer items, no layout impact)
- Achievements + Collections together (list-based pages scroll well)

**Needs mobile-specific handling:**
- **Social hub (Guild + Friends)** — two nested sub-nav levels on mobile is a UX anti-pattern. Recommendation: on screens < 640px keep Guild and Friends as separate drawer items. The merger is desktop-only. Use CSS media query to show the combined sub-tab UI on desktop and the split items in the drawer on mobile. The Capacitor wrapper will need the split behavior.
- **Arena + Tower merger** — sub-tabs work fine on mobile; the Tower leaderboard is a scrollable list that fits the mobile viewport. Safe.
- **Home page redesign** — the proposed 3-column layout is desktop-only. On mobile (< 640px), the 3 columns should stack: Player strip → Daily checklist (full width) → Command matrix 2×3 grid → Status row (horizontal scroll) → Top heroes (horizontal scroll). The current OpsPanel already uses a stack layout on mobile; the redesign should preserve that.
- **CurrencyBar on Home** — once Home adopts the shared NavBar + CurrencyBar, the currency bar will appear on mobile Home for the first time. Verify that the horizontal scroll behavior does not conflict with the existing Home scroll container on mobile. The `hide-mobile` class on the Home TopBar's currency row (line 79 of `Me.tsx`) means mobile currently shows no currency on Home at all — that is a gap worth fixing regardless.

---

## Screenshots Directory

All screenshots at `docs/screenshots/`:

| File | Page |
|------|------|
| `01-login.png` | Login / Register page |
| `02-register-filled.png` | Registration form filled |
| `03-after-register.png` | Immediately post-registration |
| `04-logged-in.png` | Logged-in state pre-audit |
| `10-home.png` | Home (`/app/me`) |
| `11-roster.png` | Roster (`/app/roster`) |
| `12-summon.png` | Summon (`/app/summon`) |
| `13-inventory.png` | Inventory (`/app/inventory`) — empty state |
| `14-shards.png` | Shards (`/app/shards`) — empty state |
| `15-crafting.png` | Crafting (`/app/crafting`) |
| `16-stages.png` | Stages (`/app/stages`) |
| `17-story.png` | Story (`/app/story`) |
| `18-arena.png` | Arena (`/app/arena`) — no opponents |
| `19-tower.png` | Tower (`/app/tower`) |
| `20-raids.png` | Raids (`/app/raids`) — empty state |
| `21-daily.png` | Daily Quests (`/app/daily`) |
| `22-battlepass.png` | Battle Pass (`/app/battle-pass`) |
| `23-shop.png` | Shop (`/app/shop`) |
| `24-guild.png` | Guild (`/app/guild`) — pre-join state |
| `25-friends.png` | Friends (`/app/friends`) — no friends |
| `26-collections.png` | Collections (`/app/collections`) |
| `27-achievements.png` | Achievements (`/app/achievements`) |
| `28-account.png` | Account (`/app/account`) |
