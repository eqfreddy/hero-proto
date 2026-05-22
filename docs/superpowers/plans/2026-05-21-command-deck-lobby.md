# Command Deck Lobby Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split `me` / `lobby` home experience with one Star-Wars-flavored command deck that routes players into the core loops through five clickable rooms.

**Architecture:** Keep the existing shared shell chrome, but make `/app/me` the single home route backed by a rebuilt `LobbyRoute`. The lobby will merge daily-routing, featured-operator presence, contextual monetization nudges, and five room cards (`Bridge`, `Holotable`, `Barracks`, `Droid Forge`, `Black Market`) that deep-link into existing routes without inventing new backend contracts.

**Tech Stack:** React, React Router, TanStack Query, existing hero/guild/raid hooks, Vitest, Vite SPA build.

---

### Task 1: Lock the new lobby contract in tests

**Files:**
- Modify: `frontend/src/routes/Lobby.test.tsx`

- [ ] **Step 1: Write the failing test**
  - Assert the new home shows `Command Deck`, `Holotable`, `Black Market`, and a daily-routing section such as `Today's Ops`.

- [ ] **Step 2: Run test to verify it fails**
  - Run: `npx vitest run src/routes/Lobby.test.tsx`
  - Expected: FAIL because the current lobby still renders the older billboard layout.

- [ ] **Step 3: Write minimal implementation**
  - Rebuild `LobbyRoute` around the new command-deck copy and five-room model.

- [ ] **Step 4: Run test to verify it passes**
  - Run: `npx vitest run src/routes/Lobby.test.tsx`
  - Expected: PASS

### Task 2: Replace the old lobby with the command deck

**Files:**
- Modify: `frontend/src/routes/Lobby.tsx`
- Modify: `frontend/src/routes/Lobby.css`

- [ ] **Step 1: Recompose data derivations**
  - Keep existing live hooks for `me`, `heroes`, `stages`, `guild`, `raid`, `daily`, `battle pass`, and `event`.
  - Derive featured operator, next objective, daily-op checklist, raid pressure, and contextual conversion pressure from existing data only.

- [ ] **Step 2: Implement the new layout**
  - Add:
    - top ticker / fleet status strip
    - bridge header with active operator and primary CTA
    - `Today's Ops` routing rail
    - five room cards with primary + secondary actions
    - exchange / spend rail with contextual nudges

- [ ] **Step 3: Restyle for the new theme**
  - Replace the scroll-heavy billboard CSS with a command-bridge / holotable look that still works inside shared shell chrome on desktop and mobile.

### Task 3: Make `/app/me` the single home and retire route drift

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Point `/app/me` at the rebuilt lobby**
  - Keep `/app/lobby` only as a redirect alias to `/app/me`.

- [ ] **Step 2: Verify home entry remains consistent**
  - Ensure existing top-left / home-nav behavior still resolves to the same route.

### Task 4: Verify, rebuild, and prep for live refresh

**Files:**
- Modify: `app/static/spa/` build output

- [ ] **Step 1: Run focused frontend verification**
  - `npx vitest run src/routes/Lobby.test.tsx src/test/shell.test.tsx src/test/me.test.tsx`
  - `npx tsc -b --pretty false`

- [ ] **Step 2: Rebuild the committed SPA output**
  - `npm run build --prefix frontend`

- [ ] **Step 3: Sanity-check local route behavior**
  - Refresh local app and confirm `/app/me` and brand/home buttons land on the command deck.
