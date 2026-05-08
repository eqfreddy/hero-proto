# Lobby Overhaul — Design Spec
**Date:** 2026-05-05  
**Status:** Approved for implementation

---

## Summary

Full redesign of the hero-proto SPA lobby. Combines three trial mockups into one unified layout: Rootlord persistent left sidebar (Trial 1 + Trial 3), zone-tab section navigation (Trial 2), three-column ops-center shell (Trial 3), and a live event log + shop right panel (Trial 3). Three separate shop sections (Coins / Gems / QoL) replace the current flat shop. All old backgrounds removed from the SPA.

---

## Visual Identity

**Two-register color system:**
- *Cyberpunk chrome* (UI shell): `#04060c` bg, `#080d18` panels, `#00ffe0` teal accents, `#ff2d78` magenta alerts, `rgba(0,255,224,0.08)` borders
- *Dark fantasy* (character elements): `#c8102e` crimson, `#ffd700` gold, `#9b30ff` void purple — used only on The Rootlord widget and rarity/faction elements

**Texture:** CSS scanline overlay (`repeating-linear-gradient`) + radial vignette. No image files.

**Typography:** Existing font for body. Headers: `letter-spacing: 0.08em`, uppercase. Terminal/log sections: monospace (`Consolas`).

---

## Layout — Three Column Shell

```
┌──────────────────────────────────────────────────────────────┐
│  TOPBAR: logo · status dot · player meta · currencies · clock│
├────────────┬───────────────────────────────────┬─────────────┤
│            │  SECTOR NAV TABS                  │             │
│  ROOTLORD  │  (Ops / Combat / Summon / Story / │  SHOP       │
│  SIDEBAR   │   Guild / Raid)                   │  (3 tabs)   │
│  220px     ├───────────────────────────────────┤  +          │
│            │  MAIN CONTENT                     │  LIVE LOG   │
│  terminal  │  (section renders per active tab) │  280px      │
│  output    │                                   │             │
│            │  Scrollable, breathing room       │             │
└────────────┴───────────────────────────────────┴─────────────┘
```

---

## Column Specs

### Left — Rootlord Sidebar (220px, fixed)
- The Rootlord card art (`app/static/heroes/cards/The_Man_The_Dev.png`) with bottom fade mask + crimson drop shadow
- Below art: terminal-style output area in monospace font
  - `root@void:~$ status --user <username>`
  - Rotating reactive quote line (6s interval, fade transition)
  - Static: `◈ THE ROOTLORD · MYTH // ROGUE_IT // DEVOPS`
- Right border: animated gradient line (crimson → teal)
- Background: subtle crimson radial glow at top

**Rootlord quote pool — state-driven (priority order):**
1. Energy ≤ 20%: `"Energy critical. sudo reboot self."`
2. Unclaimed rewards ≥ 2: `"Resources unclaimed. This is how entropy starts."`
3. Pity counter ≥ 45: `"The pity counter nears its limit. It knows what's coming."`
4. Arena losses > wins (session): `"The metrics lie. Purge the metrics."`
5. All dailies claimed: `"Efficient. The rest could learn."`
6. Default pool (cycle): sysadmin chaos quips

### Center — Zone Navigation + Content
**Sector tab strip** (sticky, `40px`):
- `⬡ Ops` · `⚔ Combat` · `🌀 Summon` · `📖 Story` · `🛡 Guild` · `🐉 Raid`
- Active tab: teal underline + teal text glow
- Badge indicator on tabs with pending actions

**Ops sector (default):**
- Player strip: avatar initials, name, faction badge, arena rating, XP bar
- Command Matrix: 3×2 grid of large action tiles (Battle, Summon, Arena, Raid, Guild, Story) — each has color accent, icon, subtitle stat, optional badge
- System Status meters: Energy bar, Pity counter, Arena rating bar
- Daily Ops table: quest rows with colored status dots, progress, reward

**Combat sector:** Arena stats table + recent match log with WIN/LOSS results

**Summon sector:** Pity counter, credits, gem cost table + summon button

**Story sector:** Chapter progress, alignment status

**Guild sector:** Guild info, contribution, member count

**Raid sector:** Boss HP bar, contribution buttons

### Right — Shop + Live Log (280px, fixed)
**Energy mini-bar** at top (always visible)

**Shop panel** with 3 selector buttons:
- 🪙 **Coins**: Free daily sack, Coin Chest (💎50), Coin Vault (💎180), Dev's Stash ($4.99)
- 💎 **Gems**: Gem Pouch ($0.99), Gem Cache ($4.99), Gem Vault ($9.99), GODMODE Bundle ($24.99)
- ⚙️ **QoL**: Energy Refill (💎50), XP Booster 24h (💎80), Shard Converter (💎100), Auto-Battle 7d ($2.99)

**Live System Log** (bottom of right col):
- Scrolling event feed: arena results, summon pulls, quest completions, guild activity
- Monospace font, colored tags `[ARENA]` `[SUMMON]` `[GUILD]` etc.
- New entries animate in at top, fade to muted after 4s
- Seeded with real data from `/me` on load; live entries appended on actions

---

## Shop Backend Additions

Current shop covers gems + shard exchange. New SKUs needed:

**Coin shop:**
- `coin_sack_daily` — free, 5,000 coins, 1/day limit
- `coin_chest` — 💎50, 25,000 coins
- `coin_vault` — 💎180, 100,000 coins
- `devs_stash` — $4.99, 500,000 coins (Stripe)

**QoL shop:**
- `energy_refill` — 💎50, full energy restore (already exists as `/me/refill-energy`, just add SKU)
- `xp_booster_24h` — 💎80, sets `xp_boost_expires_at` on Account
- `shard_converter` — 💎100, 100💎→150✦ (already exists as shard exchange, add SKU alias)
- `auto_battle_7d` — $2.99, sets `auto_battle_expires_at` (Stripe, stub for now)

---

## Removed

- All old COF SVG backgrounds from SPA routes and CSS (`bg-server-closet`, `bg-cable-hell`, etc.)
- Old Gary animation assets are not used in SPA (already absent — confirm and remove any references)
- Current `Me.tsx` two-column card grid layout — replaced entirely
- Current `Shop.tsx` flat list — replaced with tabbed shop

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/index.css` | Full theme replacement: new CSS variables, scanline, scrollbar |
| `frontend/src/components/Layout/` | Add Rootlord sidebar, three-column shell, topbar currencies |
| `frontend/src/routes/Me.tsx` | Full rewrite: player strip + zone tabs + sector panels |
| `frontend/src/routes/Shop.tsx` | Full rewrite: three-tab shop (coins/gems/qol) |
| `app/routers/shop.py` | Add coin shop SKUs + QoL SKUs |
| `app/shop.py` | Add coin purchase logic, xp_boost logic |
| `app/models.py` | Add `xp_boost_expires_at`, `auto_battle_expires_at` fields |
| `alembic/versions/` | Migration for new Account fields |

---

## Out of Scope

- New background art (user will provide; slots are stubbed as CSS-only)
- Auto-battle actual automation logic (field added, behavior stubbed)
- XP boost server-side application (field added, applied in level-up logic separately)
- Mobile/Capacitor adaptation (follow-up sprint)
