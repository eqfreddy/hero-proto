# Design brief: hero-proto — app icon + UI direction

**One-line pitch.** A gacha hero-collector MMORPG set in a *retro-IT cyberpunk* world, where the heroes are exiled sysadmins, helpdesk drones, and rogue ops who've gone underground against the megacorps. Think *Shadowrun* meets *late-90s tech support*, rendered in synthwave neons.

**Genre & mechanics.** Mobile-style gacha RPG. Players summon heroes (Common→Legendary→Myth rarity), ascend them with shards, equip gear, and run turn-based 3D battles down a circuit-board stage map. Monetization is real (Stripe live): pulls, battle pass, monthly card, gem packs.

## The three flavors that MUST coexist — do not pick one, blend them

1. **Cyberpunk synthwave.** Near-black backgrounds (`#04060c`), cyan accent (`#00ffe0`), void-purple (`#9b30ff`), warm gold (`#ffd700`), crimson alerts (`#c8102e`). Glow, scanlines, thin neon strokes, subtle CRT vibe. Not Blade Runner orange. Not Cyberpunk 2077 yellow. *Tron Legacy* + *Hotline Miami* color logic.

2. **Retro-IT humor.** Stage tier names are `Floppy Disk → Hard Disk → RAID-0 → Legen-wait-dary`. Heroes wear shirts that say "git blame everyone." Backgrounds include server closets, cable hell, fluorescent-lit cubicles. The world is *IT infrastructure as mythology* — a ticket queue is a quest log, a kernel panic is a boss fight. Dry, deadpan, Gen-X. Never zany. Never Office Space cosplay.

3. **MMORPG / faction warfare.** Three factions, ideologically loaded:
   - **RESISTANCE** (cyan/teal) — anti-corp hackers, sysadmin rebels, "information wants to be free"
   - **CORP_GREED** (gold/crimson) — megacorp enforcers, suits, polished menace
   - **EXILE** (purple/grey) — unaligned, new players, drifters who haven't picked a side

   Faction identity is visible in card frames, button gradients, and hero silhouettes.

## App-icon constraints

- Must read at 48px and 1024px.
- Single focal element. No text in the icon.
- A *symbol* that fuses the three flavors — e.g. a stylized hero glyph framed by a circuit-board node, with a single cyan/purple accent; OR a faction sigil; OR a floppy-disk silhouette reinterpreted as a shield. Do not literally show a floppy disk — the retro-IT vibe should be implied, not cosplayed.
- Avoid: anime faces, generic swords, RPG-Maker portraits, gradient blobs, "AI startup" geometric logos.

## What hero-proto is NOT

- Not anime/chibi (Genshin, Honkai aesthetic — wrong).
- Not high-fantasy (no dragons, no parchment, no Tolkien).
- Not gritty grimdark cyberpunk (no blood, no neon-red districts).
- Not corporate SaaS-clean (no flat Stripe-style minimalism).
- Not 8-bit pixel retro (the "retro" is *workplace IT 1995–2005*, not arcade).

## Tone reference stack

*Mr. Robot* color grading · *Persona 5* UI energy (rotated 90° toward circuit boards) · *Disco Elysium* dialogue dryness · early-2000s sysadmin BOFH stories · *Ready Player One* if it had taste.

## Deliverables

- (a) one app icon at 1024×1024 PNG
- (b) a 3-tile UI mood board showing how a hero card, a button, and a stage node should look
