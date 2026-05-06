# Onboarding Quest System Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep new players engaged through a week-one arc by combining a persistent floating quest checklist with per-screen coach marks, rewarded with an exclusive cosmetic frame and a meaningful currency/hero choice.

**Architecture:** Dedicated server-side quest engine (`Quest` + `AccountQuest` models) that tracks task progress via event hooks in existing endpoints. Frontend renders a floating bottom-right widget reading from `/quests/active`. Coach marks are UI-only, tracked in `localStorage`.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React/TypeScript SPA (frontend), existing `Account` reward machinery for gem/cosmetic grants.

---

## 1. Data Model

### `Quest` (static definition table)
Seeded at startup — not user-editable.

| Field | Type | Notes |
|---|---|---|
| `id` | str PK | e.g. `"onboarding_week_one"` |
| `name` | str | "Getting Started" |
| `description` | str | Flavor text |
| `tasks_json` | str | JSON array of task definitions |
| `reward_json` | str | JSON reward spec |
| `sort_order` | int | For future weekly/event ordering |

### `AccountQuest`
One row per account per active quest.

| Field | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `account_id` | int FK | |
| `quest_id` | str FK | |
| `progress_json` | str | `{task_id: current_count}` |
| `completed_at` | datetime \| null | Set when all tasks done |
| `claimed_at` | datetime \| null | Set when reward collected |
| `claim_choice` | str \| null | `"epic"` or `"gems"` |
| `dismissed` | bool | Hides widget without claiming |
| `created_at` | datetime | |

### Task definition schema (inside `tasks_json`)
```json
[
  {
    "id": "first_battle",
    "label": "Run your first battle",
    "event": "BATTLE_COMPLETE",
    "target": 1
  },
  ...
]
```

### Stage difficulty tiers

| Tier | Internal name | Display name |
|---|---|---|
| 1 | `NORMAL` | Floppy |
| 2 | `HARD` | Hard Disk |
| 3 | `LEGENDARY` | Legen'waitforit'dary |

**Legendary v1 (ship first):** Random modifier stacking — each run rolls 2-3 negative modifiers (enemy enrage at 50% HP, healer silence, escalating ATK, etc.). Same stage, different feel each attempt. Low build cost, high replayability.

**Legendary v2+ (future Legend Events):**
- **Team comp locks** — faction-only, max hero count, element restrictions. Drives roster depth; players chase heroes that unlock more stages.
- **Endless waves + leaderboard** — how far can you get? Floor milestones grant escalating rewards; floor 100 earns a cosmetic. Async competition, no real-time PvP infra required.

### Event types
`BATTLE_COMPLETE`, `BATTLE_WIN`, `SUMMON_COMPLETE`, `GEAR_EQUIPPED`, `FACTION_CHOSEN`, `ARENA_WIN`, `GUILD_JOINED`, `DAILY_QUEST_COMPLETE`, `RAID_CONTRIBUTED`, `HERO_LEVELED`, `STAGE_CLEARED`, `HARD_STAGE_CLEARED`, `LEGENDARY_STAGE_CLEARED`, `STORY_CHAPTER_CLEARED`, `ACCOUNT_LEVEL_REACHED`

---

## 2. Week-One Quest Definition

**Quest ID:** `onboarding_week_one`  
**Name:** Getting Started  
**Flavor:** *"Welcome to the corp. Here's what we need you to do before Friday."*

| # | Task | Event | Target | Day |
|---|---|---|---|---|
| 1 | Run your first battle | `BATTLE_COMPLETE` | 1 | 1 |
| 2 | Summon a hero | `SUMMON_COMPLETE` | 1 | 1 |
| 3 | Equip a gear item | `GEAR_EQUIPPED` | 1 | 1 |
| 4 | Choose your faction | `FACTION_CHOSEN` | 1 | 1 |
| 5 | Win 5 battles | `BATTLE_WIN` | 5 | 2–3 |
| 6 | Clear a story chapter | `STORY_CHAPTER_CLEARED` | 1 | 2–3 |
| 7 | Win your first arena match | `ARENA_WIN` | 1 | 2–3 |
| 8 | Join a guild | `GUILD_JOINED` | 1 | 2–3 |
| 9 | Reach account level 5 | `ACCOUNT_LEVEL_REACHED` | 5 | 2–3 |
| 10 | Complete a daily quest | `DAILY_QUEST_COMPLETE` | 1 | 4–5 |
| 11 | Contribute to a guild raid | `RAID_CONTRIBUTED` | 1 | 4–5 |
| 12 | Clear a Hard difficulty stage | `HARD_STAGE_CLEARED` | 1 | 4–5 |
| 13 | Level a hero to level 5 | `HERO_LEVELED` | 5 | 4–5 |
| 14 | Complete daily quests on 3 separate days | `DAILY_QUEST_COMPLETE` | 3 | 4–5 |
| 15 | Reach account level 10 | `ACCOUNT_LEVEL_REACHED` | 10 | 6–7 |
| 16 | Win 10 arena matches total | `ARENA_WIN` | 10 | 6–7 |
| 17 | Complete 3 story chapters | `STORY_CHAPTER_CLEARED` | 3 | 6–7 |
| 18 | Complete the first story arc | `STORY_ARC_CLEARED` | 1 | 6–7 |
| 19 | Clear a Legendary stage | `LEGENDARY_STAGE_CLEARED` | 1 | 6–7 |

**Note on task 4 (faction):** Faction choice is currently locked to level 50. For onboarding, trigger `FACTION_CHOSEN` when the player first visits the faction alignment screen, or lower the unlock to level 5 for new accounts.

**Note on task 14:** Tracks unique calendar days a daily quest was completed — not raw count. Progress stored as a set of date strings in `progress_json`.

---

## 3. Reward

**Always granted on claim:**
- `"Survived Onboarding"` cosmetic frame (exclusive — not in shop, not purchasable)
- Added to `account.cosmetic_frames` JSON array

**Player choice (mutually exclusive):**
- **Epic pull** — one guaranteed named Epic hero summon (uses existing summon machinery with `rarity_floor="EPIC"`)
- **500 gems** — added to `account.gems`

Choice is recorded in `AccountQuest.claim_choice` and cannot be changed after claiming.

---

## 4. Backend API

### New endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/quests/active` | Returns all active (unclaimed, undismissed) `AccountQuest` rows for the authed account, with full task progress |
| `POST` | `/quests/{quest_id}/claim` | Body: `{"choice": "epic" \| "gems"}`. Grants reward, sets `claimed_at`. 400 if not complete or already claimed. |
| `POST` | `/quests/{quest_id}/dismiss` | Sets `dismissed=true`. Hides widget. Can be re-shown from account settings. |

### Quest service (`app/services/quest_service.py`)

```python
def record_event(db: Session, account: Account, event: str, payload: dict) -> None:
    """Call from existing endpoints to advance quest tasks."""
```

Called from:
- `app/routers/battles.py` → `BATTLE_COMPLETE`, `BATTLE_WIN`, `STAGE_CLEARED`, `HARD_STAGE_CLEARED`, `LEGENDARY_STAGE_CLEARED`
- `app/routers/summon.py` → `SUMMON_COMPLETE`
- `app/routers/gear.py` → `GEAR_EQUIPPED`
- `app/routers/me.py` → `ACCOUNT_LEVEL_REACHED` (on level-up events)
- `app/routers/arena.py` → `ARENA_WIN`
- `app/routers/guilds.py` → `GUILD_JOINED`, `RAID_CONTRIBUTED`
- `app/routers/daily.py` → `DAILY_QUEST_COMPLETE`
- `app/routers/story.py` → `STORY_CHAPTER_CLEARED`, `STORY_ARC_CLEARED`
- `app/routers/me.py` (faction) → `FACTION_CHOSEN`

### Quest seeding
`app/quests.py` — static dict of quest definitions, seeded to DB on startup via `seed_quests(db)`. Called from `app/main.py` startup event alongside existing seed functions. New accounts auto-enroll in `onboarding_week_one` on registration (in `auth.py`).

---

## 5. Frontend — Floating Widget

**Location:** Fixed bottom-right, all authenticated screens. `z-index` above content, below modals.

**States:**

| State | Appearance |
|---|---|
| Active, tasks remaining | Dark panel, accent border, progress bar, current task highlighted |
| All tasks complete | Gold pulsing glow, "Claim Reward" CTA |
| Dismissed | Hidden. Small "?" icon bottom-right reopens it. |

**Collapsed/expanded:** Widget collapses to a slim pill (`Getting Started · 7/18`) on click. Expands to show full task list grouped by day range.

**Current task:** The next incomplete task is highlighted with `→`. Clicking it navigates to the relevant screen.

**Claim flow:**
1. Widget shows gold "Claim Reward" button when `completed_at` is set
2. Click opens the claim modal (see mockup)
3. Modal shows the always-granted frame + choice of Epic or 500 gems
4. On choice, `POST /quests/onboarding_week_one/claim` with `{choice}`
5. Success animation, confetti, frame and reward applied instantly
6. Widget enters a "completed" state and auto-hides after 5 seconds

---

## 6. Frontend — Coach Marks

**Storage:** `localStorage` key `heroproto_coachmarks_seen` — JSON array of screen IDs. No server state.

**Trigger:** On first mount of each screen (checked against `localStorage`), render a `<CoachMark>` overlay component.

**Behavior:**
- Semi-transparent dimmed overlay (`rgba(0,0,0,0.72)`)
- One element highlighted (CSS `box-shadow` ring, not DOM clone)
- Yellow tooltip bubble with ≤15-word explanation, arrow pointing at element
- "Tap anywhere to dismiss" hint at bottom
- Dismissing writes the screen ID to `localStorage`

**Screens and what to highlight:**

| Screen | Highlight | Tooltip |
|---|---|---|
| Stages | Battle button | "Tap Battle to fight a stage. Energy refills over time." |
| Summon | Pull button | "Spend shards to summon heroes. Pity guarantees an Epic at 50 pulls." |
| Inventory | Equip button | "Drag gear onto a hero slot to boost their stats." |
| Arena | Attack button | "Challenge players near your rating. Wins raise your rank." |
| Guild | Join button | "Join a guild to access raids and guild chat." |
| Daily | Quest list | "Complete daily quests to earn coins and shards. Resets at midnight." |
| Roster | Hero card | "Tap a hero to level up, ascend, or equip gear." |

---

## 7. Error Handling

- `record_event` is fire-and-forget — never raises, logs errors silently. Quest progress loss on DB error is acceptable over breaking the action that triggered it.
- Duplicate events are idempotent — `record_event` checks current progress before incrementing.
- Claiming a non-complete quest returns `400 {"detail": "quest not complete"}`.
- Claiming twice returns `400 {"detail": "already claimed"}`.
- `/quests/active` returns `[]` (not 404) if account has no active quests.

---

## 8. Future Extension Points

The `Quest` table supports future quest types with zero schema changes:
- **Weekly quests** — new rows with `id: "weekly_2026_w20"`, auto-expire via `expires_at` field (add later)
- **Event quests** — same structure, limited-time reward items
- **Guild quests** — shared `AccountQuest` rows keyed to guild membership (future)
- **Achievement-style quests** — permanent progression milestones

The `record_event` service is the single integration point — adding a new quest type only requires a new quest definition and no endpoint changes.

---

## 9. Progression Mechanics (backburner — review before Phase 4)

> Identified from level test (2026-05-06): account reached level 20 via 1,575 runs on Stage 1 at 12 XP/win. No incentive to attempt harder content. Three systems to design and implement together.

### XP scaling by difficulty

| Tier | Display name | XP per win |
|---|---|---|
| Normal | Floppy | 12 |
| Hard | Hard Disk | 28 |
| Legendary | Legen'waitforit'dary | 60 |

### Bottlenecks (intentional gates)

- **Stage tier lock** — Hard variant of a stage unlocks only after clearing its Normal version; Legendary unlocks after Hard. Per-stage, not per-account.
- **Power floor** — Legendary stages reject teams below a minimum power threshold (value TBD during balancing).
- Account-level chapter gates already exist (lvl 1 / 10 / 20 / 50) — keep as-is.

### Pity mechanics (all three ship together)

**1. Fail pity on hard stages**
Tracked per `(account_id, stage_id, tier)`. Consecutive losses increment a counter. At 3 consecutive losses: enemy HP reduced 10% for the next attempt only. Counter resets on any win. Stored in a new `stage_pity_json` column on `accounts` (or a separate `stage_pity` table). Never shown to the player as a number — just "the stage felt slightly easier."

**2. Rest XP**
Offline time accumulates a 2× XP multiplier, capped at 12 hours of offline time (= 1 full session worth of bonus). Burns off over the next session at 2× rate until exhausted. Stored as `rest_xp_banked` (int) + `rest_xp_last_tick_at` (datetime) on `accounts`. UI shows a small "rested" badge on the XP bar when active. Rewards returning players; softly discourages marathon grinding.

**3. Guaranteed drop meter (per stage)**
Each run on a stage fills a per-stage meter. At cap, the next run guarantees a rare+ gear drop regardless of RNG, then resets. Cap and meter stored in `stage_drop_pity_json` on `accounts`. Meter value and cap shown in stage UI ("Guaranteed drop in 4 runs"). Makes dry streaks feel like progress.

### Implementation note
All three share a `grant_xp` call path — rest XP multiplier applies there. Pity meter and drop meter need hooks in the battles router alongside the existing `record_event` calls. Schema additions are additive (new JSON columns or a new table), no breaking migrations.
