# Art needs — hero-proto

Living checklist of art assets needed to take the game from "JSON + text" to "looks like a game". Ranked by what unblocks the biggest visual jump per asset shipped.

Format, naming, and dimensions are suggestions — pick what's comfortable.

---

## 🎨 Style brief

**Theme:** dry-humor enterprise-IT purgatory. Think: Office Space + Dilbert + a Diablo loot screen. Heroes are IT archetypes with gear-based power fantasy. The tonal reference is the `cluster-of-fuckery` channel's Gary 2.0 character — salt-and-pepper goatee, dead eyes, holding a coffee mug or pager.

**Art style:** stick-figure-adjacent, flat vector, limited palette, readable at 64×64. The frontend is DOM-based so PNG or SVG both work. SVG preferred — scales without blur.

**Palette anchors:**
- Background: dark slate `#0b0d10` → `#14202b` (already in `battle.html`).
- Role tints: ATK `#ff7a59` (orange), DEF `#59a0ff` (blue), SUP `#6dd39a` (green). Portraits should not fight these — a neutral/muted character palette with a single accent pops best.
- Rarity frames: COMMON grey, UNCOMMON green, RARE blue, EPIC purple, LEGENDARY gold.

---

## 1. Hero portraits (25 needed — highest priority)

One 256×256 SVG (or PNG) per template code. Transparent background. Head-and-shoulders framing so it works at 64×64 in the battle card and 256×256 on the roster.

**Filename convention:** `app/static/heroes/<code>.svg`. The backend already emits `template.code` in API responses — frontend will just do `<img src="/app/heroes/${code}.svg">`.

### COMMON (3)
- [ ] `ticket_gremlin` — Ticket Gremlin. HELPDESK/ATK. Gremlin-looking intern half-buried in sticky notes.
- [ ] `printer_whisperer` — Printer Whisperer. HELPDESK/SUP. Older person cupping ear to a copier, dust mote halo.
- [ ] `overnight_janitor` — Overnight Janitor. LEGACY/DEF. Figure with mop and badge clip, fluorescent tube glow.
- [ ] `devops_apprentice` — DevOps Apprentice. DEVOPS/ATK. Hoodie kid with laptop-shield.
- [ ] `forgotten_contractor` — Forgotten Contractor. ROGUE_IT/ATK. Nondescript figure, NDA-shaped face, visitor badge.

### UNCOMMON (5)
- [ ] `jaded_intern` — Jaded Intern. HELPDESK/ATK. Dead-eyed intern with an "Unpaid" lanyard.
- [ ] `sre_on_call` — SRE on Call. DEVOPS/SUP. Pager holstered, mug labelled "RUNBOOK".
- [ ] `compliance_officer` — Compliance Officer. EXECUTIVE/DEF. Suit with a 400-page binder as a shield.
- [ ] `security_auditor` — Security Auditor. EXECUTIVE/ATK. Magnifying glass over a keyboard.
- [ ] `helpdesk_veteran` — Helpdesk Veteran. HELPDESK/DEF. Grizzled veteran wearing "I've Seen Things" T-shirt.
- [ ] `build_engineer` — Build Engineer. DEVOPS/ATK. Goggles, green-build check mark over head.

### RARE (5)
- [ ] `the_sysadmin` — The Sysadmin. LEGACY/DEF. Solid figure, sysadmin vest, keys on belt.
- [ ] `root_access_janitor` — Root-Access Janitor. ROGUE_IT/ATK. Janitor with a glowing root-ssh mop.
- [ ] `vp_of_vibes` — VP of Vibes. EXECUTIVE/SUP. Branded sweater, confetti around head.
- [ ] `keymaster_gary` — Keymaster (Gary). HELPDESK/ATK. **This is the channel's Gary 2.0** — reuse the existing character from `cluster-of-fuckery/gary2/`. Side-view pose from the Gary 2.0 set, cropped to head+shoulders.
- [ ] `rogue_dba` — Rogue DBA. ROGUE_IT/SUP. Hoodie figure whispering `DROP TABLE` over a keyboard.
- [ ] `oncall_warrior` — Oncall Warrior. DEVOPS/DEF. Knight-helmet made of a server chassis, pager in gauntlet.

### EPIC (4)
- [ ] `the_post_mortem` — The Post-Mortem. DEVOPS/SUP. Figure presenting a slide deck titled "Five Whys".
- [ ] `midnight_pager` — Midnight Pager. DEVOPS/ATK. Silhouette at 3AM with three pagers going off.
- [ ] `the_consultant` — The Consultant. EXECUTIVE/DEF. Suit with laser-pointer sword and PowerPoint shield.
- [ ] `retired_mainframe_guru` — Retired Mainframe Guru. LEGACY/SUP. Elder in a rocking chair, punch cards in lap.
- [ ] `shadow_it_operator` — Shadow IT Operator. ROGUE_IT/ATK. Hooded figure behind an unlisted VM.

### LEGENDARY (3)
- [ ] `the_founder` — The Founder. EXECUTIVE/ATK. Hoodie + blazer combo, "founder mode" aura.
- [ ] `chaos_monkey` — Chaos Monkey. DEVOPS/ATK. Literal monkey holding a `kill -9` placard.
- [ ] `the_board_member` — The Board Member. EXECUTIVE/SUP. Pinstripes, cigar, "fiduciary duty" halo.

---

## 2. Rarity frames (5 needed — quick win)

One 256×256 SVG per rarity, designed as a frame you can composite under a portrait.

- [ ] `app/static/frames/COMMON.svg` — grey, plain
- [ ] `app/static/frames/UNCOMMON.svg` — green, single-line border
- [ ] `app/static/frames/RARE.svg` — blue, double-line border
- [ ] `app/static/frames/EPIC.svg` — purple, ornate corners
- [ ] `app/static/frames/LEGENDARY.svg` — gold, animated shimmer (SVG `<animate>` is fine)

---

## 3. Faction badges (5 needed — low priority but high identity)

Small 32×32 icons shown in the corner of each portrait.

- [ ] `app/static/factions/HELPDESK.svg` — headset with coiled cord
- [ ] `app/static/factions/DEVOPS.svg` — ouroboros CI-pipeline loop
- [ ] `app/static/factions/EXECUTIVE.svg` — briefcase with dollar sign
- [ ] `app/static/factions/ROGUE_IT.svg` — unauthorized-dongle + skull
- [ ] `app/static/factions/LEGACY.svg` — floppy disk with cobwebs

---

## 4. Stage backgrounds (10 needed — medium priority)

One 1280×720 image per stage. Purely decorative — shown behind the battle arena in `battle.html`. Reuse between stages where tonally similar.

- [ ] `onboarding_day` — corporate atrium, confetti on the floor
- [ ] `first_outage` — NOC wall of red dashboards
- [ ] `quarterly_audit` — sterile glass conference room
- [ ] `legacy_server_room` — beige 90s server closet (reuse `cluster-of-fuckery/backgrounds/bg-server-closet.svg` if it's close)
- [ ] `ceos_one_on_one` — corner office at sunset
- [ ] (five more for stages 6–10 — spec out as they're designed)

---

## 5. Status-effect icons (5 needed — small, impactful)

16×16 SVG glyphs shown in the status pills on the battle card.

- [ ] `app/static/status/ATK_UP.svg` — up-arrow with fist
- [ ] `app/static/status/DEF_DOWN.svg` — down-arrow with cracked shield
- [ ] `app/static/status/POISON.svg` — green droplet with skull
- [ ] `app/static/status/STUN.svg` — dazed stars
- [ ] `app/static/status/SHIELD.svg` — blue bubble

---

## 6. UI polish (nice-to-have)

- [ ] Logo/wordmark for the header ("hero-proto")
- [ ] Loading spinner (SVG animated)
- [ ] Summon animation frames (opening card → rarity flash). 5–10 frames is enough for a spritesheet.
- [ ] Win/loss screen illustrations (one each — server-closet celebration / smoldering datacenter)
- [ ] Gear icons per slot × rarity (6 slots × 4 rarities = 24) — can start with placeholder shapes tinted by rarity.

---

## How the frontend picks these up

Once any file is dropped in `app/static/…`, the existing FastAPI mount (`app.mount("/app", StaticFiles…)`) serves it automatically at `/app/…`. No backend change needed for simple swaps; I'll wire the battle card to point at `/app/heroes/${code}.svg` with a silhouette fallback when it's time.

**Fallback plan:** while waiting on art, I can generate placeholder SVGs programmatically (role-colored silhouettes with the hero's initials). One hour of scripting. Gives every card a visual even pre-art.
