# Handoff: Battle UI — Setup, Replay, Roster

## Overview

Three new battle-related pages for the hero-proto MMORPG:
1. **Battle Setup Screen** — Stage selection + team composition (1-3 heroes)
2. **Battle Replay Viewer** — Combat log visualization with HP tracking and status effects
3. **Hero Codex (Roster)** — Browsable reference of all 25 heroes by faction/role

These are **high-fidelity HTML prototypes** showing final colors, typography, spacing, and interactions. Your task: save these three HTML files to `app/static/` and wire them to the backend API endpoints listed below.

## Fidelity

**High-fidelity (hifi)**: Pixel-perfect mockups with final colors, typography, spacing, and all interactive states. The HTML is production-ready; just replace mock data with real API calls and deploy.

## Screens / Views

### 1. Battle Setup Screen (`battle-setup.html`)

**Purpose**: Select a stage and compose a 1-3 hero team before initiating battle.

**Layout**:
- Two-column grid (1fr 1fr) on desktop, stacks on mobile
- Left: Stage list (flex column, gap 12px)
- Right: Team builder panel (static position on desktop)

**Components**:

#### Stage Cards
- Background: `linear-gradient(135deg, #16191f 0%, #0f1217 100%)`
- Border: `2px solid rgba(255,255,255,0.1)`
- Border-radius: `8px`
- Padding: `16px`
- Hover: Border becomes `#59a0ff`, shadow `0 4px 12px rgba(0,0,0,0.4)`
- Selected: Background `#59a0ff`, text color `#000`
- Locked: Opacity `0.5`, cursor `not-allowed`

**Stage Meta**: Font 10px, color `#8a9aac`, flex row with 12px gap

**Stage Power Badge**: Font 11px bold, color `#ffd86b`, bg `rgba(255,216,107,0.15)`, padding 4px 8px, border-radius 4px

#### Team Slots
- Background: `rgba(255,255,255,0.04)` empty, `rgba(89,160,255,0.15)` filled
- Border: `2px dashed rgba(255,255,255,0.15)` empty, `rgba(89,160,255,0.3)` filled
- Border-radius: `8px`
- Min-height: `70px`
- Filled slots show hero name (12px bold #fff), role/faction/power (9px #6a7a8c)
- Remove button (✕) appears on hover: `32x32px`, bg `rgba(255,122,89,0.2)`, color `#ff7a59`

#### Team Power Display
- 2-column grid showing total team power and average hero power
- Label: 9px uppercase `#6a7a8c`
- Value: 14px bold `#ffd86b`

#### Buttons
- Clear Team: bg `rgba(255,255,255,0.1)`, border `1px solid rgba(255,255,255,0.2)`, color `#ddd`
- Fight: bg `#59a0ff`, color `#000`, padding 12px 24px, font 12px bold
- Fight disabled when team size is 0 or >3, or stage not selected

#### Hero Picker Modal
- Fixed overlay: `rgba(0,0,0,0.8)`
- Modal bg: `linear-gradient(135deg, #16191f 0%, #0f1217 100%)`
- Hero grid: `repeat(auto-fill, minmax(140px, 1fr))`, gap 12px
- Each hero card: portrait placeholder (56x56px), name (10px bold), role (8px uppercase)
- Filter buttons: Faction + "All Heroes"

**Interactions & Behavior**:
- Click stage card (if not locked) → select it, highlight blue
- Click team slot (empty) → open hero picker modal
- Click hero in modal → add to selected slot, close modal
- Click remove button on filled slot → remove hero
- Click clear button → reset team and stage selection
- Fight button click → log battle params, show alert (replace with POST /battles)

**State Management**:
- `selectedStage`: null or stage id
- `team`: [null, null, null] — array of hero ids
- `slotBeingFilled`: index of team slot being edited
- `heroFilter`: "all" or faction name

**Data Fetching**:
- Mock data provided (lines 180-210 in HTML)
- Replace with:
  - `GET /stages` → array of stage objects
  - `GET /heroes/mine` → array of owned heroes
  - `POST /battles { stage_id, team: [id1, id2, id3] }` → returns `{ id, ... }`, redirect to `/app/battle-replay.html?id={id}`

---

### 2. Battle Replay Viewer (`battle-replay.html`)

**Purpose**: Display a completed battle with live HP updates, status effects, and a filterable combat log.

**Layout**:
- Battle arena: flex row (gap 40px), left/right teams on desktop, stacks on mobile
- Combat log: scrollable container (max-height 400px, overflow-y auto)
- Rewards grid: `repeat(auto-fit, minmax(120px, 1fr))`

**Components**:

#### Unit Cards (Allies & Enemies)
- Background: `rgba(255,255,255,0.04)`
- Border: `2px solid rgba(255,255,255,0.1)`
- Border-radius: `8px`
- Padding: `12px`
- Width: `180px`
- Dead state: opacity `0.5`, border `rgba(255,122,89,0.3)`

**Unit Portrait**: 64x64px, bg `rgba(89,160,255,0.15)`, border-radius 6px, displays initials

**Unit Name**: 12px bold #fff

**Unit Role**: 8px uppercase #6a7a8c

**HP Bar**:
- Height: 6px
- Background: `rgba(255,255,255,0.1)`
- Fill: `linear-gradient(90deg, #6dd39a, #4ba377)`, width = (current_hp / max_hp) * 100%
- Transition: `width 300ms ease`

**Status Icons** (16x16px, 8px font):
- ATK_UP: bg `rgba(255,122,89,0.3)`, color `#ff7a59`
- DEF_DOWN: bg `rgba(255,100,100,0.3)`, color `#ff6464`
- POISON: bg `rgba(109,211,154,0.3)`, color `#6dd39a`
- STUN: bg `rgba(255,216,107,0.3)`, color `#ffd86b`
- SHIELD: bg `rgba(89,160,255,0.3)`, color `#59a0ff`

#### Combat Log
- Entry bg: `rgba(255,255,255,0.04)`, border-left 3px, padding 10px 12px
- Text: 11px, color `#aaa`, line-height 1.4
- Strong text: color `#fff`, font-weight 700
- Border colors by type:
  - DAMAGE: `#ff7a59`
  - HEAL: `#6dd39a`
  - DEATH: `#ff6464`
  - SPECIAL: `#c77dff`
  - STATUS_APPLIED: `#ffd86b`

#### Filter Buttons
- Active: bg `#59a0ff`, color `#000`, border `#59a0ff`
- Inactive: bg `rgba(89,160,255,0.15)`, border `rgba(89,160,255,0.3)`, color `#59a0ff`

#### Rewards Section
- Grid of reward items (coins, XP, shards)
- Icon: 24px emoji
- Label: 9px uppercase `#6a7a8c`
- Value: 14px bold `#ffd86b`

**Interactions & Behavior**:
- Log filter buttons toggle event type (All / Damage / Heal / Status / Deaths)
- HP bars animate as log is processed
- Status icons appear/disappear as they're applied/expired
- Outcome badge shows WIN/LOSS/DRAW with appropriate colors

**State Management**:
- `unitStates`: { uid: { hp, max_hp, dead, statuses: [] }, ... }
- `currentFilter`: "all" or event type

**Data Fetching**:
- Mock data provided (lines 415-490 in HTML)
- Replace with:
  - `GET /battles/{id}` where `id` comes from URL query param `?id=N`
  - Parse battle log and render progressively

---

### 3. Hero Codex / Roster (`roster.html`)

**Purpose**: Browse all 25 hero templates by faction or role.

**Layout**:
- Filter bar: flex row, gap 12px, flex-wrap wrap
- Roster grid: `repeat(auto-fill, minmax(200px, 1fr))`, gap 16px

**Components**:

#### Roster Cards
- Background: `linear-gradient(135deg, #16191f 0%, #0f1217 100%)`
- Border: `2px solid rgba(255,255,255,0.08)`
- Border-radius: `12px`
- Padding: `14px`
- Hover: Border `var(--primary-color)`, shadow `0 8px 20px rgba(0,0,0,0.5)`, transform `translateY(-2px)`

**Rarity Badge**: 9px bold, padding 3px 8px, border-radius 6px
- COMMON: `#7d8a9c`
- UNCOMMON: `#6dd39a`
- RARE: `#59a0ff`
- EPIC: `#c77dff`
- LEGENDARY: `#ffd86b`

**Hero Name**: 14px bold #fff

**Hero Class (Faction)**: 10px uppercase `#8a9aac`

**Role Badge**: 8px bold, padding 3px 8px, border-radius 4px
- ATK: bg `rgba(255,122,89,0.15)`, color `#ff7a59`
- DEF: bg `rgba(89,160,255,0.15)`, color `#59a0ff`
- SUP: bg `rgba(109,211,154,0.15)`, color `#6dd39a`

**Stats Grid**: 2 columns, font 9px, color `#8a9aac`
- HP, ATK, DEF, SPD

#### Filter Buttons
- Active: bg `#59a0ff`, border `#59a0ff`, color `#000`
- Inactive: border `rgba(255,255,255,0.1)`, color `#ddd`

**Interactions & Behavior**:
- Click filter to show only heroes of that faction/role
- Cards are non-interactive (reference view only)

**State Management**:
- `currentFilter`: "all" or faction/role code

---

## Design Tokens

### Colors
- Primary Blue: `#59a0ff`
- Success Green: `#6dd39a`
- Warning Yellow: `#ffd86b`
- Danger Red: `#ff7a59`
- Purple: `#c77dff`
- Dark BG: `#0b0d10`
- Card BG: `#16191f` (with gradient)
- Text Primary: `#fff`
- Text Secondary: `#ddd`
- Text Tertiary: `#8a9aac`
- Text Disabled: `#6a7a8c`

### Faction Colors
- HELPDESK: `#ff7a59`
- DEVOPS: `#59a0ff`
- EXECUTIVE: `#c77dff`
- ROGUE_IT: `#ffd86b`
- LEGACY: `#6dd39a`

### Typography
- Font Family: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- H1: 32-36px, bold (800), letter-spacing 0
- Section Title: 16px, bold (800), uppercase, letter-spacing 0.5px
- Card Title: 12-14px, bold (700-800), color #fff
- Label: 9-10px, uppercase, letter-spacing 0.3-0.5px
- Body: 10-11px, color #aaa / #ddd

### Spacing
- Gaps: 8px, 12px, 16px, 20px, 24px, 32px, 40px
- Padding: 12px, 16px, 20px, 24px
- Border-radius: 4px (small), 6px (medium), 8px (buttons/cards), 12px (modals)

### Shadows
- Card hover: `0 8px 20px rgba(0,0,0,0.5)`
- Modal: `0 4px 12px rgba(0,0,0,0.4)`
- None on default state

### Transitions
- Default: `all 200ms ease`
- HP bar: `width 300ms ease`

---

## Assets

No external image assets required. All UI uses:
- Solid colors and gradients
- CSS borders and shadows
- Text labels and initials (no portraits)

Status effect icons fall back to text initials (A, D, P, S, SH) if SVG assets missing.

---

## Files

1. **battle-setup.html** (19.2 KB)
   - Lines 180-210: Mock stages and heroes
   - Line 265: Fight button click handler — replace with POST /battles

2. **battle-replay.html** (19.3 KB)
   - Lines 415-490: Mock battle data
   - Line 515: Initial render — replace with GET /battles/{id}

3. **roster.html** (10.8 KB)
   - Lines 343-361: Hero character data
   - Self-contained; no API calls needed

---

## Integration Checklist

- [ ] Copy three HTML files to `app/static/`
- [ ] Add JWT auth: read from `localStorage.heroproto_jwt`, attach as Bearer token
- [ ] Wire endpoints:
  - `GET /stages` (battle-setup.html, line 180)
  - `GET /heroes/mine` (battle-setup.html, line 190)
  - `POST /battles { stage_id, team }` (battle-setup.html, line 265)
  - `GET /battles/{id}` (battle-replay.html, line 415) — read `id` from URL `?id=N`
- [ ] Update routing:
  - Stages tab → `battle-setup.html`
  - Battle history link → `battle-replay.html?id={battleId}`
  - (Optional) Hero menu → `roster.html`
- [ ] Create placeholder status effect SVGs (5 files):
  - `/app/static/status/ATK_UP.svg`
  - `/app/static/status/DEF_DOWN.svg`
  - `/app/static/status/POISON.svg`
  - `/app/static/status/STUN.svg`
  - `/app/static/status/SHIELD.svg`
- [ ] Retire `battle.html` (keep `battle-phaser.html` as optional animated version)

---

## Notes for Developer

- All three pages are **standalone HTML** — no framework dependencies, just vanilla JS + CSS
- Mock data is clearly marked with comments; find-and-replace to swap in real API calls
- Pages are responsive but designed for desktop first
- Status icons use CSS classes and text fallback (no SVG required for MVP)
- Battle setup enforces 1-3 hero team limit (per backend schema)
- Combat log can handle large battles; scroll container keeps it bounded
