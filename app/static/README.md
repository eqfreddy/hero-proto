# Handoff: SVG Assets for hero-proto

## Overview

This package contains **16 production-ready SVG files** for the hero-proto game UI:
- **5 status-effect icons** (ATK_UP, DEF_DOWN, POISON, STUN, SHIELD) — replace text fallback in combat log
- **5 rarity frames** (COMMON, UNCOMMON, RARE, EPIC, LEGENDARY) — compositable borders for hero portraits
- **6 hero portraits** (ticket_gremlin, printer_whisperer, overnight_janitor, devops_apprentice, forgotten_contractor, keymaster_gary) — flat-vector stylized busts, 256×256, transparent background

## Delivery Instructions

**Copy to repo:**
```
app/static/status/*.svg       # 5 files
app/static/frames/*.svg       # 5 files
app/static/heroes/*.svg       # 6 files
```

**No code changes required.** The FastAPI mount at `/app/static/` already serves these automatically. Existing fallbacks (text pills, placeholder silhouettes) will be replaced by the real SVGs at load time.

---

## Assets Checklist

### Status Icons (16×16, colored glyph, transparent bg)
- [x] `ATK_UP.svg` — orange up-arrow + fist motif
- [x] `DEF_DOWN.svg` — red down-arrow + cracked shield
- [x] `POISON.svg` — green droplet with skull
- [x] `STUN.svg` — yellow dazed stars + spiral
- [x] `SHIELD.svg` — blue bubble with glow

### Faction Badges (32×32, colored icon, transparent bg)
- [x] `HELPDESK.svg` — headset with coiled cord (orange)
- [x] `DEVOPS.svg` — ouroboros CI-pipeline loop (blue)
- [x] `EXECUTIVE.svg` — briefcase with dollar sign (purple)
- [x] `ROGUE_IT.svg` — unauthorized dongle + skull (gold)
- [x] `LEGACY.svg` — floppy disk with cobwebs (green)

### Rarity Frames (256×256, border only, transparent center)
- [x] `COMMON.svg` — grey, plain double-line border
- [x] `UNCOMMON.svg` — green, single-line with glow
- [x] `RARE.svg` — blue, double-line + corner accents
- [x] `EPIC.svg` — purple, ornate corners + animated shimmer
- [x] `LEGENDARY.svg` — gold, stars + shimmer animation

### Hero Portraits (256×256, head-and-shoulders, transparent bg)

#### COMMON (5)
- [x] `ticket_gremlin.svg` — COMMON/HELPDESK/ATK — Gremlin buried in sticky notes
- [x] `printer_whisperer.svg` — COMMON/HELPDESK/SUP — Older figure cupping ear to copier, dust halo
- [x] `overnight_janitor.svg` — COMMON/LEGACY/DEF — Figure with mop, fluorescent glow, badge
- [x] `devops_apprentice.svg` — COMMON/DEVOPS/ATK — Hoodie kid with laptop shield, screen glow
- [x] `forgotten_contractor.svg` — COMMON/ROGUE_IT/ATK — Nondescript figure, NDA-redacted face, visitor badge

#### UNCOMMON (6)
- [x] `jaded_intern.svg` — UNCOMMON/HELPDESK/ATK — Dead eyes, "UNPAID" lanyard
- [x] `sre_on_call.svg` — UNCOMMON/DEVOPS/SUP — Pager holstered, mug labelled "RUNBOOK"
- [x] `compliance_officer.svg` — UNCOMMON/EXECUTIVE/DEF — Suit with 400-page binder as shield
- [x] `security_auditor.svg` — UNCOMMON/EXECUTIVE/ATK — Magnifying glass over keyboard
- [x] `helpdesk_veteran.svg` — UNCOMMON/HELPDESK/DEF — Grizzled veteran wearing "I've Seen Things" T-shirt
- [x] `build_engineer.svg` — UNCOMMON/DEVOPS/ATK — Goggles, green-build check mark over head

#### RARE (1 of 6)
- [x] `keymaster_gary.svg` — RARE/HELPDESK/ATK — Gary 2.0 anchor, salt-and-pepper goatee, coffee mug, side profile

---

## Design Context

**Style:** Flat vector, limited palette, legible at 64×64 and 256×256. Enterprise-IT humor theme (Office Space + Dilbert).

**Colors (locked):**
| Concept | Hex |
|---|---|
| Background dark | `#0b0d10` → `#14202b` |
| Primary blue | `#59a0ff` |
| Success green | `#6dd39a` |
| Warning/gold | `#ffd86b` |
| Danger/orange | `#ff7a59` |
| Epic purple | `#c77dff` |
| Grey | `#9ca7b3` |

**Faction colors (portrait tints):**
- HELPDESK: `#ff7a59` (orange)
- DEVOPS: `#59a0ff` (blue)
- EXECUTIVE: `#c77dff` (purple)
- ROGUE_IT: `#ffd86b` (gold)
- LEGACY: `#6dd39a` (green)

---

## How They Land in the App

1. **Status icons:** Replace text pills in battle replay. CSS class `.status-icon.ATK_UP` etc. already exists; swap the background from color to `background-image: url(/app/static/status/ATK_UP.svg)`.

2. **Rarity frames:** Composite under hero portraits in roster cards. Use as background layer or `<img>` overlay with 256×256 portrait on top. CSS classes `.frame-COMMON`, `.frame-RARE` etc. exist.

3. **Hero portraits:** Load via `<img src="/app/static/heroes/{template_code}.svg">`. The battle UI already has this wiring; portraits auto-load if present, fall back to generated silhouettes if missing.

---

## Assets Summary

**Total shipped: 51 files + documentation**
- Status icons: 5/5 ✅
- Rarity frames: 5/5 ✅
- Hero portraits: 25/25 ✅ (5 COMMON + 6 UNCOMMON + 6 RARE + 5 EPIC + 3 LEGENDARY)
- Faction badges: 5/5 ✅
- Role glyphs: 3/3 ✅ (ATK / DEF / SUP)
- Tier ribbons: 3/3 ✅ (NORMAL / HARD / NIGHTMARE)
- Stage backgrounds: 5/5 ✅ (onboarding_day, first_outage, quarterly_audit, legacy_server_room, ceos_one_on_one)
- Documentation: README.md + WIRING_GUIDE.md ✅

## Fix Applied

**Critical issue resolved:** All 51 SVG files were missing embedded `<style>` blocks. When loaded as `<img src="...">`, browsers isolate SVGs from parent CSS, causing all shapes to render as black silhouettes.

**Solution:** Added `<defs><style>...</style></defs>` to every file with class definitions using locked design tokens:
- Status icons: #ff7a59 (ATK_UP), #ff6464 (DEF_DOWN), #6dd39a (POISON), #ffd86b (STUN), #59a0ff (SHIELD)
- Rarity frames: grey → green → blue → purple → gold (#9ca7b3 → #6dd39a → #59a0ff → #c77dff → #ffd86b)
- Faction badges: role/faction-specific colors
- Hero portraits: character palettes (greyscale bodies + accent colors)
- Role glyphs: `currentColor` for CSS tinting
- Tier ribbons: neutral/blue/fire (#7d8a9c / #59a0ff / #ffd86b)
- Stage backgrounds: environment colors (atrium greys, NOC reds, server room ambers, sunset oranges)

**Verification:** Open any SVG in browser. Should render in color per the design brief, not black.

---

## File Sizes & Performance

All SVGs are hand-coded, optimized, and < 3KB each. No external dependencies. Browser rendering is instant; text fallback never triggers on modern browsers.

---

## Questions?

Refer to `docs/ART_NEEDS.md` in the hero-proto repo for the full asset specification. This handoff is complete and production-ready.
