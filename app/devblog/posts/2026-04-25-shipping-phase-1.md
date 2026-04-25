---
title: Shipping Phase 1 — first 10 minutes feel good
date: 2026-04-25
summary: A guided tutorial flow, real roster grid, team presets, dedicated Summon tab, starter pack — the dashboard now feels like a game instead of a JSON dump.
author: hero-proto dev
---

Phase 1 of the PRD just shipped (commit range `5fb47c5` → `aa8c275`). Six sub-sections, six commits, 275 tests green, and an end-to-end acceptance test that walks a fresh account through nine steps without a single human click.

## What changed

### 1.1 Guided first-session flow
A new "Next step" CTA card on the `/me` tab walks new players from registration → tutorial → first summon → first real battle. Tutorial completion now grants `+1 free summon credit` (a new column on `Account`), consumed by `/summon/x1` *before* shards. Registration auto-grants 3 random COMMON heroes so the tutorial battle isn't a dead end.

### 1.2 Roster redesign
The Roster tab was a list. Now it's a rarity-tabbed grid (All / COMMON / UNCOMMON / RARE / EPIC / LEGENDARY / MYTH) with rarity-bordered cards, duplicate collapse (`Jaded Intern ×3`), and a bottom-sheet detail overlay. Click a card → see the full trading-card art, stats, signature move. Real art for the pilot 5 heroes; placeholder fallback for the 31 still in queue.

### 1.3 Team presets
`POST /me/team-presets` creates named team presets (max 5). Battle / Arena / Raid tabs get a preset dropdown plus "🕘 Use last team" pulling from the most recent successful battle. After a victory, "💾 Save team" prompts for a name and stashes the team for next time.

### 1.4 Dedicated Summon tab
Promoted from a card on `/me` to its own top-nav tab. Shows the standard banner, pity progress bar with "13 more pulls until guaranteed EPIC" copy, recent-pulls feed, and the limited-time Jump-Ahead Bundle when eligible.

### 1.5 Jump-Ahead Bundle
New SKU: `starter_jumpahead`, $4.99, one-time per account, 7-day window. Contents: 500 gems + 50 shards + 3 access cards + Keymaster Gary (RARE). No EPIC or LEGENDARY in the pack — those stay gacha-only.

### 1.6 Polish
The header "signed in as X" pill turns green when authenticated and shows the player's email prefix. Old summon-card JS removed from `/me` since the Summon tab owns it now.

## What the acceptance test does

Single test, end-to-end:

```python
def test_phase1_end_to_end(client) -> None:
    # 1. Register, see /app/.
    # 2. Confirm tutorial-not-cleared + 3 starter heroes.
    # 3. Win the tutorial, see "+1 free summon" grant.
    # 4. Open Summon tab, confirm pity counter + starter-pack card.
    # 5. Use the free summon, shards untouched.
    # 6. Open Roster, see rarity tabs + grid cards.
    # 7. Save a team preset.
    # 8. Read it back via /me/team-presets and /me/last-team.
    # 9. Buy starter pack; second purchase 409s on per-account-limit.
```

All nine steps green. If any future commit breaks the flow, this test catches it before deploy.

## What's not in Phase 1

- **Hero detail depth** (weapon/armor slots, skill tree, star-up flow with dupe selection) — Phase 2
- **Story campaign + account-level XP** — Phase 2.5
- **Combat-control overhaul** (player target selection, mana resource, hail-mary at low HP) — Phase 3
- **Animated battle actors** — Phase 3 (Rive)
- **Capacitor mobile wrap + store submission** — Phase 4

## What's next

Phase 2 prep is underway. Top of the queue is the hero detail page V2 (weapon/armor slots, skill-up flow, sell button) — every player session involves the roster, and that's the biggest UX dead-zone left.

If you want to follow along, [/changelog](/changelog) auto-renders the git history with category badges. Or watch the GitHub repo.
