# Battle Visuals — Stack Picks

Goal: get the Phaser battle replay viewer (`app/static/battle-phaser.html`) from "static portraits with HP bars" to "I want to *watch* this fight." Three full stacks below — pick one, ship one. Don't mix mid-stream.

Locked-in constraint: **Phaser 3 stays.** The deterministic event-log replay model already works (one battle = one JSON log → one `applyEvent()` switch). All picks have to plug into that pipeline.

---

## Combat-event shopping list (what we have to render)

Every visual choice has to cover these events from `app/combat.py`. Cards already ship; the column on the right is what's missing today.

| Event in log | Currently | Needs |
|---|---|---|
| `TURN` | yellow ring fade-in | + idle-loop on the actor sprite |
| `DAMAGE` (BASIC / SPECIAL / AOE / BOSS_PHASE) | container shake + frame red flash + "-N" float | attacker lunge anim + defender hit-react anim |
| `HEAL` (single + AOE_HEAL) | "+N" green float | green pulse + heal-glow particles |
| `STATUS_APPLIED` (POISON / BURN / FREEZE / STUN / HEAL_BLOCK / REFLECT / SHIELD / ATK_UP / DEF_DOWN) | text pill below the unit | per-status overlay (ice block, fire particles, ❌ over heart, mirror ring, gold up-arrow, etc.) |
| `STATUS_EXPIRED` / `STATUS_BROKEN` | nothing | shatter / fade out |
| `DEATH` | KO stamp + fade to 0.3 alpha | death anim → tombstone or sit-down |
| `REVIVE` / `AOE_REVIVE` | nothing | rise-up anim + sparkle |
| `REFLECT` (bounce-back damage event) | nothing | beam from defender to attacker |
| `SPECIAL` (named) | yellow caption + ring | full-screen freeze frame + name banner + cinematic camera |
| `BOSS_PHASE` (3 raid bosses) | identical to AOE_DAMAGE | bigger camera shake + signature VFX per boss |
| `FACTION_SYNERGY` | (no current handler) | one-time banner at battle start ("HELPDESK x3 → +10% ATK") |
| `END` | result text | victory pose / defeat pose per side |

Plus stage backgrounds (currently flat gradient) and a soundtrack/SFX layer that doesn't exist at all.

---

## Plan A — All-Free, Already-Owned ⭐ recommended starter

**The bet:** you already own a stick-figure rig pipeline in `cluster-of-fuckery/`. Use it. Stick figures are explicitly green-lit in `TODO.md` ("better than silhouettes"), they match the YouTube channel's brand, and the assets feed both products.

| Layer | Pick | Cost | Why |
|---|---|---|---|
| **Animation rigs** | cluster-of-fuckery `tween-poses.js` extended to render sprite sheets per role × animation | $0 | You wrote it. Backgrounds + 10 poses + 5 expressions already exist. Renders via `@resvg/resvg-js`. |
| **Engine** | Phaser 3.80 (already in use) + `Phaser.AnimationManager` for sprite-sheet playback | $0 | Native, zero new deps. Frame-based animation is overkill-proof for our event cadence. |
| **VFX / particles** | Phaser built-in `ParticleEmitterManager` (status overlays, heal sparkles, hit impact) | $0 | Ships with Phaser, [docs](https://docs.phaser.io/phaser/concepts/particles). |
| **Backgrounds** | `cluster-of-fuckery/backgrounds/bg-*.svg` (8 already exist: server-closet, cable-hell, cubicle, IT-corner, break-room, hallway, boss-office, storage) | $0 | Map stage → background. Already authored, on-brand. |
| **Audio (SFX)** | [Howler.js](https://howlerjs.com) — free MIT | $0 | Best web audio lib, drop-in. |
| **Audio (music)** | OpenGameArt loops, CC0 only | $0 | Filter to "battle" / "tense" / "victory". |
| **Status icons** | Hand-drawn 32×32 PNGs (8-10 statuses) — fits the existing `app/static/status/` folder | $0 | One afternoon in any pixel editor, or generate via the existing card prompt style. |

**Time to ship MVP:** ~3-4 working days.
- Day 1: extend cluster-of-fuckery with `render-rpg-rig.js` → outputs `<role>_<anim>.png` sprite sheets (idle / attack / hit / death / special / victory). Six animations × three roles = 18 sheets.
- Day 2: wire `Phaser.AnimationManager` into `battle-phaser.html`; replace the static portrait `Image` with a `Sprite` playing the right anim per event.
- Day 3: status overlays + particle bursts + background swap by stage_id.
- Day 4: Howler hookup, polish camera shake, faction-synergy banner.

**Pros**
- Single-author pipeline, no new tools to learn
- Style matches the YouTube channel (free cross-promotion)
- All assets are yours forever
- Cheapest possible escape from "static portraits"

**Cons**
- Frame-by-frame sheets balloon repo size (each anim ~200KB × 18 sheets ≈ 4MB)
- No per-character flair beyond shirt text + pose — every ATK looks similar in motion
- Stick figures don't "wow"; they read as "intentional placeholder"

**Escalation trigger:** if play-testers say *"the fight is fine but the heroes feel interchangeable,"* skip to **Plan B**.

---

## Plan B — Free Skeletal Polish (mid-tier)

**The bet:** swap the frame-by-frame sheets for skeletal animation so one rig drives many heroes via skin-swap. Smooth interpolation, fewer assets per character.

| Layer | Pick | Cost | Why |
|---|---|---|---|
| **Animation rigs** | [DragonBones](https://dragonbones.github.io/en/animation.html) — free editor, free runtime, JSON export | $0 | Spine's free competitor, mesh deform supported, [phaser plugin still updated Dec 2025](https://github.com/raksa/phaser-dragonbones). |
| **Engine** | Phaser 3.80 + [`raksa/phaser-dragonbones`](https://github.com/raksa/phaser-dragonbones) plugin | $0 | Phaser-blessed plugin, drop-in `addArmature("hero_atk")`. |
| **Rigs** | 3 base rigs (ATK / DEF / SUP) with portrait-as-head skin slot. Each rig: idle, attack_basic, attack_special, hit, death, victory | $0 | One author-week to ship 3 polished rigs. Skin-swap the head per hero from your existing 1050×1498 cards. |
| **VFX / particles** | Phaser built-in particles + DragonBones bone-attached effects | $0 | Bone events fire mid-animation (e.g. on the "swing" frame) — perfect for spawning a slash particle exactly when the sword arc peaks. |
| **Backgrounds** | cluster-of-fuckery `bg-*.svg` (same as Plan A) | $0 | Reuse. |
| **Audio** | Howler.js + OpenGameArt (same as Plan A) | $0 | Reuse. |
| **Status icons** | Same 32×32 PNG set | $0 | Reuse. |

**Time to ship MVP:** ~7-10 working days.
- Days 1-3: learn DragonBones editor; build the ATK rig (idle + 5 actions). Use the cards as head skins.
- Day 4: ATK rig in Phaser, plays the right anim per event.
- Days 5-6: DEF + SUP rigs.
- Days 7-8: skin-swap pipeline (hero_code → which head image gets attached to which slot).
- Days 9-10: VFX, status overlays, polish.

**Pros**
- Smoother movement than frame sheets
- ~8 KB of JSON per rig + a small atlas — repo stays slim
- Bone events let you sync particles exactly to action peaks
- Looks closer to mobile-game polish without paying

**Cons**
- DragonBones editor learning curve (~2 days for a rigging novice)
- Plugin is community-maintained, not first-party (Phaser ships native Spine support but **not** native DragonBones)
- Three rigs ≠ thirty bespoke heroes. Every ATK still moves identically; only the head changes.

**Escalation trigger:** if you hit a polish ceiling and the budget allows, jump to **Plan C**.

---

## Plan C — Premium Polish (paid option)

**The bet:** spend $379 on Spine Pro, gain industry-standard tooling, get the "this looks like a real game" feel.

| Layer | Pick | Cost | Why |
|---|---|---|---|
| **Animation rigs** | [Spine Professional](https://esotericsoftware.com/spine-purchase) (one-time license, includes meshes + IK + skins) | **$379 one-time** | Industry standard. AAA hero collectors run on Spine. Mesh deform = jiggly cloth, weighty hits. |
| **Engine** | Phaser 3.80 + [`spine-phaser-v4`](https://github.com/EsotericSoftware/spine-runtimes/tree/4.2/spine-ts) — the **runtime is free MIT**, only the editor is paid | $0 (runtime) | First-party support, Esoteric Software ships it. |
| **Rigs** | Same 3-rig structure (ATK/DEF/SUP) but with mesh + IK. Per-hero skin = head + accessory swap. | (license-time only) | Spine's mesh deform handles capes, hair, weapon trails natively. |
| **VFX / particles** | Phaser particles **+** [GSAP](https://gsap.com) free tier for cinematic timelines on BOSS_PHASE | $0 | GSAP nests timelines cleanly — bossfight choreography becomes scriptable. |
| **Backgrounds** | cluster-of-fuckery + commissioned upgrade pass for raid stages | $0-$500 (optional) | Optional bump on the 3 raid stages where it matters. |
| **Audio (music)** | Royalty-free music library subscription ([Soundstripe](https://www.soundstripe.com) ~$15/mo or one-time stems) | $15-100 | Themed tracks per faction. |
| **Audio (SFX)** | Howler.js + bespoke SFX pack ([gamesounds.xyz](https://gamesounds.xyz) free or [Soniss GDC bundle](https://sonniss.com/gameaudiogdc) free yearly drops) | $0 | Same lib, better source assets. |
| **Status icons** | Commissioned 64×64 set, animated (idle bobbing flame for BURN, etc.) | $50-200 (Fiverr) | Cheaper than Spine, big polish lift. |

**Total cost:** **$379 one-time + optional ~$50-200 SFX/icon polish**. Well under $700 even loaded up.

**Time to ship MVP:** ~10-14 working days.
- Days 1-2: Spine learning curve + import a card.
- Days 3-7: build ATK / DEF / SUP rigs with mesh + IK + skin slots.
- Days 8-10: Phaser wiring, status FX, BOSS_PHASE cinematic timeline (GSAP).
- Days 11-14: polish, tune timing, music + SFX.

**Pros**
- Indistinguishable-from-AAA visual ceiling
- Mesh deform handles wind, cape, hair, weapon trails for free
- First-party Phaser support (not a community plugin)
- License is **one-time** — no subscription rot
- Resaleable skill if the project pivots (Spine is a CV item)

**Cons**
- $379 sunk before you know if you'll ship
- Spine has a steeper learning curve than DragonBones
- Likely overkill for the alpha audience size
- Premium polish exposes weaknesses elsewhere (UI / sound / balance)

**When to actually pull this trigger:** *only* if Plan B shipped, the game has measurable retention (>10% D7 or whatever target), and battle visuals are the next-largest user-perceived bottleneck.

---

## Side-by-side

| | Plan A (cluster-of-fuckery) | Plan B (DragonBones) | Plan C (Spine Pro) |
|---|---|---|---|
| **Cost** | $0 | $0 | $379 one-time + opt. extras |
| **Days to MVP** | 3-4 | 7-10 | 10-14 |
| **Engine** | Phaser 3 | Phaser 3 + community plugin | Phaser 3 + first-party runtime |
| **Animation tech** | Frame-by-frame sprite sheets | Skeletal (DragonBones JSON) | Skeletal + mesh deform (Spine) |
| **Style match** | ⭐⭐⭐ on-brand stick figures | ⭐⭐ generic skeletal | ⭐⭐⭐ AAA polish |
| **Asset reuse from project** | High (cluster-of-fuckery + cards + bgs) | Mid (cards as head skins) | Mid (cards as head skins) |
| **Author bandwidth** | One-author pipeline | New tool to learn | Steeper tool to learn |
| **Per-hero uniqueness** | Limited | Limited (head swap) | Limited (head + skin slot) |
| **Repo bloat** | ~4 MB sheets | ~50 KB JSON + small atlas | ~50 KB JSON + small atlas |
| **Sound stack** | Howler + OpenGameArt | Howler + OpenGameArt | Howler + curated music + bespoke SFX |
| **Particles** | Phaser native | Phaser native + bone events | Phaser native + bone events + GSAP timelines |
| **Backgrounds** | cluster-of-fuckery 8 SVGs | cluster-of-fuckery 8 SVGs | cluster-of-fuckery + optional commissioned pass |
| **First-party Phaser support?** | ✅ all native | ❌ community plugin | ✅ Esoteric ships it |
| **Escalation cost** | Just throw it away — it cost a week | DragonBones rigs not portable to Spine | Terminal — Spine Pro is the ceiling |
| **Risk if you stop mid-stream** | Low (sheets work standalone) | Mid (need plugin updates) | Mid (need to amortize $379) |

---

## Recommendation

**Ship Plan A.** Then re-evaluate.

Concrete reasoning:
1. The art pipeline already exists in `cluster-of-fuckery/` — the marginal cost of producing the sprite sheets is tiny.
2. Stick figures are explicitly endorsed in the existing TODO.md product-direction notes — no aesthetic mismatch with the channel's brand.
3. The hardest part of "battle visuals" isn't the rig — it's the **event-to-VFX wiring**. That work is identical across all three plans, so do it now on the cheapest base.
4. Plan A's deliverables are useful evals: if they look bad, you'll have specific "this is what's wrong" feedback that informs whether DragonBones or Spine fixes it. Without playing Plan A first, the upgrade is a guess.
5. The $379 Spine cost isn't the issue. The opportunity cost of two extra weeks before you know if combat is fun is the issue.

**Hard rule for upgrading:** don't move to Plan B/C until **a real user (not you) tests Plan A and says the visuals specifically are the bottleneck.** Until then, every dev day spent on rigs is a day not spent on combat depth, anti-cheat, or shipping.

---

## What I'd do first if you say go

Single PR, one commit, ~1 day:

1. Add `cluster-of-fuckery/render-rpg-rig.js` — CLI that takes `--role atk|def|sup --animation idle|attack|hit|death|special|victory --frames 8` and renders an N-frame sprite sheet PNG to `cluster-of-fuckery/scenes/rigs/<role>_<animation>.png`.
2. Add `scripts/copy-rigs-to-hero-proto.sh` — one-shot copies the sheets into `app/static/heroes/sprites/`.
3. Wire `Phaser.AnimationManager` into `battle-phaser.html`: replace `portrait.setDisplaySize(64,64)` with `Sprite` + `play("idle")` on `TURN`, `play("attack")` on outgoing `DAMAGE`, etc.
4. Smoke test: replay an existing battle ID, confirm each event triggers the right animation. Commit.

After that ships, you have a baseline to judge against — and Plans B/C become an informed bet, not a guess.
