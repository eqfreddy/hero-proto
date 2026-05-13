# stages-board.html — Design Notes

## Key Design Decisions

**Snaking path layout** — nodes snake left→right / right→left in rows of 5, mirroring AFK Arena's chapter map. Bezier connectors bend gently at row transitions, making the path readable without a full Phaser/canvas renderer. SVG `animateMotion` drives data-packet sprites along cleared paths for zero JS overhead.

**Node state hierarchy** — six distinct visual states: cleared (green glow + score badge), ready (cyan pulse ring + READY badge), locked (muted, cursor:not-allowed), milestone gate (purple glow, animated when claimable), boss (crimson ring, larger), vault (dashed cyan outline + breathe animation). States map directly to the backend `cleared` / `unlocked` fields from Stages.tsx.

**Side panel** doubles as the action context — the board is a navigation device, not the primary information surface. Selected node drives panel content; fight button is always in the same spot to reduce scanning.

## Rule #1 Psychology Principles

| Element | Principle |
|---|---|
| "X stages to next milestone" progress bar in panel | **Zeigarnik** — unfinished loops feel incomplete; the count pulls players one more stage |
| Gate Gamma pulsing glow + header countdown badge | **Anticipation** — reward is visible and imminent before it's reachable |
| Legendary Boss Shard row + 12% published odds | **Variable rewards** — honest odds maintain trust while keeping excitement; the shimmer animation makes it feel present on every stage |
| READY badge + cyan pulse on node 13 | **Competence** — the next correct action is unambiguous; player always knows what to do |
| "Streak resets in HH:MM:SS" header pill | **Loss aversion** — real-time countdown on an existing possession (streak) drives sessions |

## What is NOT in the Mockup (React impl needs)

- **Data fetching** — `useStages()` hook, React Query cache, optimistic `cleared` state after battle return
- **Mobile layout** — board needs horizontal scroll with touch-swipe + bottom-sheet side panel on small screens
- **Animation timing** — `animateMotion` packets need `begin` staggered via JS after stage data loads; right now offset is hardcoded per index
- **Tier switching** — each tier (Hard Disk, RAID-0, Legendary) has its own stage set; needs separate board renders or lazy node injection
- **Milestone claim API call** — PATCH `/stages/milestone/{id}/claim` with shard credit write-back
- **Board scroll-to-ready** — on mount, `scrollIntoView` the ready node so players land on their current position
- **Accessibility** — ARIA roles on nodes (`role="button"`, `aria-label`), keyboard nav (arrow keys traverse path), `prefers-reduced-motion` disables `animateMotion` packets
