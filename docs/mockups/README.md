# UI mockups — design reference, not shipping code

This folder holds interactive HTML mockups produced by design-AI sessions. They are **reference material** for sprint implementation, not pages shipped to users.

## Workflow

1. Design AI delivers a mockup HTML → saved here.
2. Sprint implementer opens the file in a browser to see the intended interaction + visual language.
3. Implementer translates the design to Jinja partials in `app/templates/partials/` against our actual data model.
4. Palette + data-shape reconciliation is done during translation (see per-file review notes below).

**Never link directly to these files from the live app** — mock data, palette mismatches, and placeholder copy mean they're not safe to surface.

---

## Files

### `heroes_rarity_grid.html` — roster redesign (Sprint F target)

Comprehensive interactive mockup: rarity-tabbed grid + bottom-sheet detail overlay. Delivered 2026-04-24 via chat, captured here for Sprint F reference.

**What's reusable:**
- Layout: `grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))` + 2-col mobile fallback.
- Card structure: portrait slot (top, aspect-ratio 1.2), info section (name + faction badge row, role + level row, power/stars/copies stack).
- Rarity border + gradient-background + glow shadow combo per tier.
- Rarity tab strip with horizontal scroll on mobile.
- Bottom-sheet detail overlay slide-up animation (`cubic-bezier(0.34, 1.56, 0.64, 1)`).
- Ascension-dots progression indicator with `next` state.

**What to reconcile during port to Jinja:**
- **Faction colors in the mockup don't match our palette.** Mockup used `#ff7a59` for HELPDESK, `#59a0ff` for DEVOPS, etc. — the AI rotated the assignments. Use the palette from `app/templates/base.html` instead. Correct mapping:
  - HELPDESK → `#4ea1ff` (blue)
  - DEVOPS → `#6dd39a` (green)
  - LEGACY → `#c97aff` (purple)
  - EXECUTIVE → `#ffd86b` (gold)
  - ROGUE_IT → `#ff6b4a` (red)
  - **MYTH** → needs its own color, not `#ff7a59` (conflicts with ROGUE_IT). Suggest `#ff66c4` (magenta/pink) or a holographic gradient.
- **Star cap** — mockup shows 7 stars; our model caps at 5.
- **Stats grid** in the detail panel shows "ATK / DEF / SUP" as stat categories; those are *roles*, not stats. Our heroes have `hp`, `atk`, `def`, `spd`. Reshape the grid accordingly.
- **Action buttons** ("Level Up" / "Ascend") — aspirational. Phase 1 says detail modal is read-only; defer wired actions to Phase 2.
- **Portrait slot** — currently renders `name.charAt(0)`. Swap in the hero bust PNGs (`/app/static/heroes/<code>_bust.png`) when they arrive.
- **Copy progress** (`copies / maxCopies`) — data not in our model yet. Either add an aggregation endpoint for same-template-count, or defer until Phase 2 where ascension UI comes in.

**How to open:**
Just double-click `heroes_rarity_grid.html` in the OS file manager — pure static HTML, no server required.
