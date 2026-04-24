# SVG Asset Wiring Guide

This guide walks Claude Code through integrating the 27 SVG assets into hero-proto. **No new dependencies** — all changes are HTML/CSS swaps.

---

## 1. Status Icons (5 SVGs)

**What:** Replace text pills with icon images in combat log.

**Files to edit:**
- `app/templates/partials/arena.html`
- `battle-replay.html` (design reference)

**Current pattern (example):**
```html
<span class="status-pill ATK_UP">A</span>
```

**New pattern:**
```html
<span class="status-pill ATK_UP">
  <img src="/app/static/status/ATK_UP.svg" alt="ATK_UP" width="16" height="16" />
</span>
```

**Implementation:**
1. In both files, find all status effect rendering (search for `status-pill` or status effect names: ATK_UP, DEF_DOWN, POISON, STUN, SHIELD)
2. Replace text content with `<img src="/app/static/status/{kind}.svg" alt="{kind}" width="16" height="16" />`
3. Keep the outer `<span>` for styling; the image replaces the text child
4. Text fallback (alt attribute) is automatic

**Effort:** ~3 lines per file (one find-replace per file, or loop if rendering is templated)

---

## 2. Faction Badges (5 SVGs) — *Optional*

**What:** Add faction icons to hero roster filter chips and portrait corners.

**Files to edit:**
- `app/templates/battle.html` or roster codex view
- `battle-replay.html` (design reference)

**Current pattern (example):**
```html
<span class="faction-filter HELPDESK">HELPDESK</span>
```

**New pattern:**
```html
<span class="faction-filter HELPDESK">
  <img src="/app/static/factions/HELPDESK.svg" alt="HELPDESK" width="32" height="32" />
  <span>HELPDESK</span>
</span>
```

**Implementation:**
1. Find faction filter/badge rendering
2. Prepend `<img src="/app/static/factions/{faction}.svg" alt="{faction}" width="32" height="32" />`
3. Update CSS for `.faction-filter` to use `display: flex; align-items: center; gap: 8px;` if needed

**Effort:** ~2–3 lines per location

---

## 3. Role Glyphs (3 SVGs, if shipped) — *Optional*

**What:** Replace text role badges (ATK, DEF, SUP) with icons.

**Files to edit:**
- Any template rendering role pills

**Current pattern:**
```html
<span class="role-badge ATK">[ATK]</span>
```

**New pattern:**
```html
<span class="role-badge ATK">
  <img src="/app/static/roles/ATK.svg" alt="ATK" width="16" height="16" />
</span>
```

**Implementation:**
1. Search for role badge rendering
2. Replace text with `<img src="/app/static/roles/{role}.svg" alt="{role}" width="16" height="16" />`

**Effort:** ~2 lines per file

---

## 4. Tier Ribbons (3 SVGs, if shipped) — *Optional*

**What:** Add difficulty tier visual badges to stage/challenge cards.

**Files to edit:**
- Stage card templates

**Current pattern:**
```html
<div class="stage-card">
  <span class="tier-badge">HARD</span>
  <!-- ... -->
</div>
```

**New pattern:**
```html
<div class="stage-card">
  <img src="/app/static/tiers/HARD.svg" alt="HARD" width="32" height="16" class="tier-ribbon" />
  <!-- ... -->
</div>
```

**CSS addition:**
```css
.tier-ribbon {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 32px;
  height: 16px;
}
```

**Effort:** ~2 lines HTML + 6 lines CSS

---

## 5. Rarity Frames (5 SVGs)

**What:** Composite a rarity-specific frame border behind hero portrait images.

**Files to edit:**
- `app/templates/battle.html` (battle card templates)
- `battle-replay.html` (design reference)
- CSS stylesheet (main or scoped)

**Current pattern (example):**
```html
<div class="hero-card">
  <img src="/app/static/heroes/ticket_gremlin.svg" alt="Ticket Gremlin" class="portrait" />
</div>
```

**New pattern:**
```html
<div class="hero-card rarity-frame-COMMON">
  <img src="/app/static/heroes/ticket_gremlin.svg" alt="Ticket Gremlin" class="portrait" />
</div>
```

**CSS addition:**
```css
/* Rarity frame backgrounds */
.rarity-frame-COMMON {
  background-image: url('/app/static/frames/COMMON.svg');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.rarity-frame-UNCOMMON {
  background-image: url('/app/static/frames/UNCOMMON.svg');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.rarity-frame-RARE {
  background-image: url('/app/static/frames/RARE.svg');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.rarity-frame-EPIC {
  background-image: url('/app/static/frames/EPIC.svg');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.rarity-frame-LEGENDARY {
  background-image: url('/app/static/frames/LEGENDARY.svg');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

/* Ensure portrait sits on top of frame */
.hero-card .portrait {
  position: relative;
  z-index: 1;
}
```

**Implementation:**
1. Find hero card / portrait container divs
2. Add class `rarity-frame-{rarity}` (where `{rarity}` is the hero's rarity: COMMON, UNCOMMON, RARE, EPIC, LEGENDARY)
3. Add the 5 CSS rules above to the stylesheet
4. Adjust sizing/positioning if needed (frames are 256×256; adjust `.hero-card` size to match)

**Effort:** ~15 lines CSS + 1 class attribute per card (or templated via `class="rarity-frame-{{ hero.rarity }}"`)

---

## 6. Hero Portraits

**What:** Load real SVG portraits from `/app/static/heroes/` instead of fallback initials.

**Files to edit:**
- `battle-replay.html` (design reference — currently shows initials)
- Phaser replayer (`battle.html`) already handles this; no changes needed

**Current pattern (battle-replay.html, example):**
```html
<div class="portrait-initials">TG</div>
```

**New pattern:**
```html
<img 
  src="/app/static/heroes/ticket_gremlin.svg" 
  alt="Ticket Gremlin" 
  class="portrait" 
  onerror="this.style.display='none'; /* show fallback initials div */"
/>
<div class="portrait-initials" style="display: none;">TG</div>
```

**Or (cleaner, with fallback on 404):**
```html
<picture>
  <source srcset="/app/static/heroes/ticket_gremlin.svg" type="image/svg+xml" />
  <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 256 256'%3E%3Ctext x='128' y='140' font-size='48' text-anchor='middle' fill='%239ca7b3'%3ETG%3C/text%3E%3C/svg%3E" alt="Ticket Gremlin" class="portrait" />
</picture>
```

**Or (JS, if templated):**
```javascript
function getHeroPortrait(heroCode, heroName) {
  const initials = heroName.split(' ').map(w => w[0]).join('').toUpperCase();
  return `
    <img 
      src="/app/static/heroes/${heroCode}.svg" 
      alt="${heroName}" 
      class="portrait"
      onerror="this.parentElement.classList.add('portrait-fallback')"
    />
    <div class="portrait-initials" aria-hidden="true">${initials}</div>
  `;
}
```

**CSS for fallback:**
```css
.portrait-fallback .portrait {
  display: none;
}

.portrait-fallback .portrait-initials {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  font-weight: bold;
  color: #9ca7b3;
}
```

**Implementation:**
1. In `battle-replay.html`, replace the initials-only rendering with an `<img>` tag pointing to `/app/static/heroes/{heroCode}.svg`
2. Add a fallback mechanism (onerror, picture, or CSS) so initials show if the SVG 404s
3. Test with a hero that has an SVG (e.g., ticket_gremlin) and one that doesn't (to verify fallback)

**Effort:** ~5–10 lines per portrait (or 10 lines of JS if templated)

---

## Testing Checklist

After wiring:

- [ ] Status icons render in arena.html
- [ ] Status icons render in battle-replay.html
- [ ] Rarity frames appear behind hero portraits
- [ ] Hero portraits load from `/app/static/heroes/*.svg`
- [ ] Hero portraits fall back to initials if SVG is missing (404)
- [ ] Faction badges appear (if implemented)
- [ ] Role glyphs appear (if implemented)
- [ ] Tier ribbons appear (if implemented)
- [ ] No console errors
- [ ] SVGs scale correctly at 64×64 (small) and 256×256 (large)

---

## File Locations

All SVG files are in `app/static/`:
```
app/static/
├── status/
│   ├── ATK_UP.svg
│   ├── DEF_DOWN.svg
│   ├── POISON.svg
│   ├── STUN.svg
│   └── SHIELD.svg
├── frames/
│   ├── COMMON.svg
│   ├── UNCOMMON.svg
│   ├── RARE.svg
│   ├── EPIC.svg
│   └── LEGENDARY.svg
├── factions/
│   ├── HELPDESK.svg
│   ├── DEVOPS.svg
│   ├── EXECUTIVE.svg
│   ├── ROGUE_IT.svg
│   └── LEGACY.svg
├── heroes/
│   ├── ticket_gremlin.svg
│   ├── printer_whisperer.svg
│   ├── overnight_janitor.svg
│   ├── devops_apprentice.svg
│   ├── forgotten_contractor.svg
│   ├── jaded_intern.svg
│   ├── sre_on_call.svg
│   ├── compliance_officer.svg
│   ├── security_auditor.svg
│   ├── helpdesk_veteran.svg
│   ├── build_engineer.svg
│   └── keymaster_gary.svg
└── [roles/ and tiers/ not yet shipped]
```

---

## Questions?

- All SVGs are ~100% opaque by default; they composite cleanly.
- Rarity frames are designed with transparent centers so portraits show through.
- Status icons are 16×16, faction/role badges are 32×32, portraits are 256×256.
- No external CSS framework needed; all wiring is vanilla HTML + CSS.
