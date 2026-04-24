# Art needs — hero-proto

Living checklist. If you drop a file in the right place, the app picks it up automatically — no code change needed.

**Status (as of last commit): zero assets landed.** All heroes currently render as placeholder silhouettes generated on the fly by `/app/placeholder/hero/<code>.svg`. Status effects render as single-letter text pills. Tier + role indicators render as text.

---

## 🥇 Recommended first batch (11 files → biggest visible jump)

If you're ordering art piecemeal, do these first. Covers the onboarding experience + the replay viewer:

| # | File | Why it matters now |
|---|---|---|
| 1 | `app/static/status/ATK_UP.svg` | Combat replay currently shows "A" text pill |
| 2 | `app/static/status/DEF_DOWN.svg` | ...shows "D" |
| 3 | `app/static/status/POISON.svg` | ...shows "P" |
| 4 | `app/static/status/STUN.svg` | ...shows "S" |
| 5 | `app/static/status/SHIELD.svg` | ...shows "SH" |
| 6 | `app/static/heroes/ticket_gremlin.svg` | Stage-1 enemy, 100% of new players fight it |
| 7 | `app/static/heroes/printer_whisperer.svg` | Stage-1 enemy + common starter pull |
| 8 | `app/static/heroes/overnight_janitor.svg` | COMMON tank, early team staple |
| 9 | `app/static/heroes/devops_apprentice.svg` | COMMON DevOps — faction coverage |
| 10 | `app/static/heroes/forgotten_contractor.svg` | COMMON ROGUE_IT — faction coverage |
| 11 | `app/static/heroes/keymaster_gary.svg` | RARE, the Gary 2.0 anchor character |

Status icons = 16×16 SVG (colored glyph, transparent bg). Hero portraits = 256×256 SVG, head-and-shoulders, transparent bg.

After this batch, the remaining 19 hero portraits are the next grind — prioritize by rarity (COMMON → LEGENDARY) so you match the pity flow a new player experiences.

---

## 🎨 Style brief

**Theme:** dry-humor enterprise-IT purgatory. Think Office Space + Dilbert + a Diablo loot screen. Heroes are IT archetypes with gear-based power fantasy. Tonal anchor is the `cluster-of-fuckery` channel's Gary 2.0 character — salt-and-pepper goatee, dead eyes, coffee mug or pager prop.

**Art style:** flat vector, limited palette, legible at 64×64 as well as 256×256. SVG preferred (scales cleanly). PNG works but loses the responsive win.

**Design tokens** (locked in; use these hex values — they're referenced throughout the UI):

| Concept | Color |
|---|---|
| Background dark | `#0b0d10` → `#14202b` gradient |
| Card background | `#14181e` / `#1b2430` |
| Accent / primary blue | `#59a0ff` |
| Success green | `#6dd39a` |
| Warning yellow / gold | `#ffd86b` |
| Danger / damage red-orange | `#ff7a59` |
| Epic purple | `#c77dff` |

**Faction colors** (use for faction badges + tinting):

| Faction | Color | Flavor |
|---|---|---|
| HELPDESK | `#ff7a59` | frontline ticket grinders |
| DEVOPS | `#59a0ff` | oncall warriors, pager goblins |
| EXECUTIVE | `#c77dff` | VPs, consultants, compliance suits |
| ROGUE_IT | `#ffd86b` | shadow-IT, unauthorized tools |
| LEGACY | `#6dd39a` | mainframe gurus, janitors, sysadmins |

**Role treatment** (silhouette / pose, not necessarily color — role glyphs below can tint):

| Role | Color | Visual cue |
|---|---|---|
| ATK | `#ff7a59` | leaner silhouette, aggressive stance |
| DEF | `#59a0ff` | broader, hunched, "solid" stance |
| SUP | `#6dd39a` | healing/casting poses, tool-in-hand |

**Rarity frames** (border/glow treatment per rarity tier):

| Rarity | Color |
|---|---|
| COMMON | `#9ca7b3` (grey) |
| UNCOMMON | `#6dd39a` (green) |
| RARE | `#59a0ff` (blue) |
| EPIC | `#c77dff` (purple) |
| LEGENDARY | `#ffd86b` (gold, optional shimmer) |

---

## Asset catalog

### 1. Hero portraits — 27 needed (0 / 27 shipped)

Filename convention: **`app/static/heroes/<template_code>.svg`**. The `template_code` is the value from `app/seed.py` `HERO_SEEDS` — it appears unchanged in every API response and every battle log, so your filename is the final filename, no renaming later.

256×256, transparent background, head-and-shoulders. Must be legible scaled to 64×64 (used on battle cards + roster grid). Must not fight the role/faction/rarity colors — keep the character palette relatively muted with one accent prop/color.

#### COMMON (5)
- [ ] `ticket_gremlin` — Ticket Gremlin — HELPDESK/ATK — Gremlin-looking intern half-buried in sticky notes
- [ ] `printer_whisperer` — Printer Whisperer — HELPDESK/SUP — Older person cupping ear to a copier, dust mote halo
- [ ] `overnight_janitor` — Overnight Janitor — LEGACY/DEF — Figure with mop and badge clip, fluorescent tube glow
- [ ] `devops_apprentice` — DevOps Apprentice — DEVOPS/ATK — Hoodie kid with laptop-shield
- [ ] `forgotten_contractor` — Forgotten Contractor — ROGUE_IT/ATK — Nondescript figure, NDA-shaped face, visitor badge

#### UNCOMMON (6)
- [ ] `jaded_intern` — Jaded Intern — HELPDESK/ATK — Dead-eyed intern with an "Unpaid" lanyard
- [ ] `sre_on_call` — SRE on Call — DEVOPS/SUP — Pager holstered, mug labelled "RUNBOOK"
- [ ] `compliance_officer` — Compliance Officer — EXECUTIVE/DEF — Suit with a 400-page binder as a shield
- [ ] `security_auditor` — Security Auditor — EXECUTIVE/ATK — Magnifying glass over a keyboard
- [ ] `helpdesk_veteran` — Helpdesk Veteran — HELPDESK/DEF — Grizzled veteran wearing "I've Seen Things" T-shirt
- [ ] `build_engineer` — Build Engineer — DEVOPS/ATK — Goggles, green-build check mark over head

#### RARE (6)
- [ ] `the_sysadmin` — The Sysadmin — LEGACY/DEF — Solid figure, sysadmin vest, keys on belt
- [ ] `root_access_janitor` — Root-Access Janitor — ROGUE_IT/ATK — Janitor with a glowing root-ssh mop
- [ ] `vp_of_vibes` — VP of Vibes — EXECUTIVE/SUP — Branded sweater, confetti around head
- [ ] `keymaster_gary` — Keymaster (Gary) — HELPDESK/ATK — **Reuses Gary 2.0 from `cluster-of-fuckery/gary2/`.** Side-view cropped to head+shoulders
- [ ] `rogue_dba` — Rogue DBA — ROGUE_IT/SUP — Hoodie figure whispering `DROP TABLE` over a keyboard
- [ ] `oncall_warrior` — Oncall Warrior — DEVOPS/DEF — Knight-helmet made of a server chassis, pager in gauntlet

#### EPIC (5)
- [ ] `the_post_mortem` — The Post-Mortem — DEVOPS/SUP — Figure presenting a slide deck titled "Five Whys"
- [ ] `midnight_pager` — Midnight Pager — DEVOPS/ATK — Silhouette at 3AM with three pagers going off
- [ ] `the_consultant` — The Consultant — EXECUTIVE/DEF — Suit with laser-pointer sword and PowerPoint shield
- [ ] `retired_mainframe_guru` — Retired Mainframe Guru — LEGACY/SUP — Elder in a rocking chair, punch cards in lap
- [ ] `shadow_it_operator` — Shadow IT Operator — ROGUE_IT/ATK — Hooded figure behind an unlisted VM

#### LEGENDARY (3)
- [ ] `the_founder` — The Founder — EXECUTIVE/ATK — Hoodie + blazer combo, "founder mode" aura
- [ ] `chaos_monkey` — Chaos Monkey — DEVOPS/ATK — Literal monkey holding a `kill -9` placard
- [ ] `the_board_member` — The Board Member — EXECUTIVE/SUP — Pinstripes, cigar, "fiduciary duty" halo

**Fallback:** any hero without art renders via `/app/placeholder/hero/<code>.svg` — a role-colored silhouette with the hero's initials. Works fine indefinitely; portraits are a polish upgrade, not a blocker.

### 2. Status-effect icons — 5 needed (0 / 5 shipped)

**Highest-ROI 5-file batch.** The replay viewer currently falls back to single-letter text pills (`A`, `D`, `P`, `S`, `SH`) — swapping to proper icons is an instant quality bump.

16×16 SVG, colored glyph, transparent background.

- [ ] `app/static/status/ATK_UP.svg` — orange up-arrow + fist motif
- [ ] `app/static/status/DEF_DOWN.svg` — red down-arrow + cracked shield
- [ ] `app/static/status/POISON.svg` — green droplet with skull
- [ ] `app/static/status/STUN.svg` — yellow dazed stars
- [ ] `app/static/status/SHIELD.svg` — blue bubble

### 3. Rarity frames — 5 needed (0 / 5 shipped)

256×256 SVG per rarity, designed as a **frame you composite under a portrait**. Transparent center; border+glow only.

- [ ] `app/static/frames/COMMON.svg` — grey, plain
- [ ] `app/static/frames/UNCOMMON.svg` — green, single-line border
- [ ] `app/static/frames/RARE.svg` — blue, double-line border
- [ ] `app/static/frames/EPIC.svg` — purple, ornate corners
- [ ] `app/static/frames/LEGENDARY.svg` — gold, animated shimmer (SVG `<animate>` tags are fine — the browser handles it)

### 4. Faction badges — 5 needed (0 / 5 shipped)

Small 32×32 icons shown in the corner of each portrait + as filter chips in the roster codex.

- [ ] `app/static/factions/HELPDESK.svg` — headset with coiled cord
- [ ] `app/static/factions/DEVOPS.svg` — ouroboros CI-pipeline loop
- [ ] `app/static/factions/EXECUTIVE.svg` — briefcase with dollar sign
- [ ] `app/static/factions/ROGUE_IT.svg` — unauthorized-dongle + skull
- [ ] `app/static/factions/LEGACY.svg` — floppy disk with cobwebs

### 5. Role glyphs — 3 needed (optional polish)

Not in the original art list. Currently ATK/DEF/SUP appear as colored text pills (`[ATK]`, `[DEF]`, `[SUP]`). SVG glyphs would sharpen the roster + battle cards.

16×16 SVG, single-color (the role tint is applied via CSS).

- [ ] `app/static/roles/ATK.svg` — sword / strike motif
- [ ] `app/static/roles/DEF.svg` — shield motif
- [ ] `app/static/roles/SUP.svg` — plus-cross / crosshair motif

### 6. Difficulty tier badges — 3 needed (optional polish)

Also text pills today (`NORMAL`, `HARD`, `NIGHTMARE`). Tier ribbons overlaid on stage cards would make the progression visual.

32×16 SVG "ribbon" per tier.

- [ ] `app/static/tiers/NORMAL.svg` — grey subtle ribbon
- [ ] `app/static/tiers/HARD.svg` — blue bolder ribbon
- [ ] `app/static/tiers/NIGHTMARE.svg` — gold + fire treatment

### 7. Stage backgrounds — 10 needed (medium priority)

1280×720 PNG or SVG per stage. Purely decorative — shown behind the battle arena in `battle-replay.html` and `battle-phaser.html`. Reuse tonally similar ones freely. HARD-tier stages reuse their NORMAL counterpart's background.

- [ ] `onboarding_day` — corporate atrium, confetti on the floor
- [ ] `first_outage` — NOC wall of red dashboards
- [ ] `quarterly_audit` — sterile glass conference room
- [ ] `legacy_server_room` — beige 90s server closet (reuse `cluster-of-fuckery/backgrounds/bg-server-closet.svg` if close)
- [ ] `ceos_one_on_one` — corner office at sunset
- [ ] (five more for stages 6-10 — will fill in once stage 6+ naming is locked; current seed has `ceos_one_on_one` at stage 5 and stops there)

### 8. UI polish — nice-to-have

Not blocking anything. In rough priority order:

- [ ] Logo / wordmark for the header ("hero-proto" or final product name)
- [ ] Loading spinner (animated SVG)
- [ ] Summon animation frames (opening card → rarity flash — 5–10 frames is enough for a spritesheet or CSS keyframe)
- [ ] Win / loss screen illustrations (one each — server-closet celebration / smoldering datacenter)
- [ ] Gear slot icons per slot × rarity (6 slots × 4 rarities = 24 — can start with 6 slot glyphs that are tinted by rarity via CSS, cuts the count to 6)
- [ ] Currency icons (coins, 💎 gems, ✦ shards, 🎫 access cards) — currently Unicode/emoji; proper SVG would look cleaner

---

## How the frontend picks these up

FastAPI mounts `app/static/` at `/app/static/` — any file at `app/static/<category>/<name>.svg` is served at `https://.../app/static/<category>/<name>.svg` with no code change.

**Portrait fallback wiring** (already in place): the Phaser battle replayer preloads both `/app/static/heroes/<code>.svg` (your art) and `/app/placeholder/hero/<code>.svg` (generated silhouette). If the real art loaded, it's used; otherwise the placeholder kicks in. So shipping portraits one at a time is safe — the page never breaks.

**Status icons / frames / faction badges / role glyphs / tier ribbons** currently have text fallbacks baked into the templates. When you drop in SVGs, the templates need a small edit to reference them — ping me to wire it up, or follow the pattern in `battle-replay.html` for status icons.

---

## Delivery order — summary

1. **11-file first batch** (5 status icons + 5 COMMON heroes + Gary) → onboarding + replay polish
2. **Next 6 hero portraits** (UNCOMMONs) → mid-game coverage
3. **Rarity frames + faction badges** (10 files) → full portrait treatment
4. **Remaining 14 hero portraits** (RARE + EPIC + LEGENDARY) → endgame + reward visuals
5. **Role glyphs + tier ribbons** (6 files) → UI polish pass
6. **Stage backgrounds + UI polish** → long tail

Total pipeline: ~68 files if you want everything. Minimum viable: the 11-file first batch is a real visual win.
