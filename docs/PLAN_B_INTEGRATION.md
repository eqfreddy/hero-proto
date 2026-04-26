# Plan B — DragonBones integration roadmap

**Status:** greenlit 2026-04-26 after the user reviewed the demo at
`/app/static/dragonbones-demo/index.html` and confirmed the Mecha 1004B
sample animations are the right level of polish.

This doc captures the open architectural decisions and the rough work
order so we can resume without re-litigating.

---

## What's already done

- Combat resolver emits an event log with everything the rig needs:
  `DAMAGE` (with `via=BASIC|SPECIAL` + `channel=melee|ranged`), `DEATH`,
  `STATUS_APPLIED/EXPIRED/BROKEN`, `BOSS_PHASE`, `HAIL_MARY`,
  `FACTION_SYNERGY`, `REFLECT`, `LIFESTEAL`, `REVIVE_BLOCKED`, etc.
- Phaser-based viewer (`app/static/battle-phaser.html`) already
  consumes that log and renders melee lunges, status tints, damage
  popups, BOSS_PHASE / HAIL_MARY / FACTION_SYNERGY cinematics, etc.
- DragonBones runtime + sample armature ships in
  `app/static/dragonbones-demo/`.
- Animation vocabulary in the sample (`idle / walk / hit / death /
  attack_01 / skill_01..05 / victory`) maps 1:1 onto the resolver
  event types.

## Open decisions (need your call before we ship code)

### 1. Engine path

Three ways to get DragonBones into the live battle viewer:

**A. Swap the viewer from Phaser to Pixi 8.x** — cleanest long-term.
Pixi has first-party DragonBones support via `pixi-dragonbones-runtime`.
We rewrite `battle-phaser.html` against Pixi using the existing log
event handlers as a starting point. Roughly a 2-day cost for the
swap + parity (re-implementing the lunges, popups, cinematic effects
we already polished in Phaser). After that, every new rig drops in
clean.

**B. Keep Phaser, add the `raksa/phaser-dragonbones` plugin** — least
disruptive. The plugin gives us `addArmature()` inside the existing
Phaser scene. Risk: community-maintained plugin, last meaningful
update Dec 2025. Could break on a future Phaser upgrade. ~half-day to
wire, but every Phaser version bump is a roll of the dice.

**C. Run DragonBones in a Pixi instance embedded inside the Phaser
scene** — both engines share a canvas, Phaser draws backgrounds /
particles / UI, Pixi draws the rigs. Two-engine complexity but lets
us reuse all the existing Phaser polish without porting. Probably 1
day to plumb but adds ongoing maintenance burden.

**Recommendation:** A. Pixi 8 is the future; the port pays for itself
the first time we add a new effect.

### 2. Rig source

You said in the design notes you have **Moho** + **Adobe 2025 full
suite**. That gives us two ways to produce DragonBones-compatible
output:

**i. Native DragonBones editor.** Free, dedicated, opens straight to
the runtime format we already have working. ~2 days learning curve
for a rigging novice. Best long-term if we'll ship many rigs.

**ii. Moho or Adobe Animate + DragonBones export.** Moho ships an
SWF/XFL export that DragonBones can re-import via its tooling.
Trickier round-trip, but lets you stay in tools you already know.
Worth a 1-hour spike — if your existing Moho character files convert
cleanly, this saves the editor learning curve.

**Recommendation:** spike Moho export first; if it round-trips
cleanly, stay in Moho. If it loses anything (mesh deform, IK), bite
the editor learning curve.

### 3. Rig shape

Three minimum rigs for v1: ATK / DEF / SUP. Each rig:

- 5 actions: `idle`, `attack_basic`, `attack_special`, `hit`, `death`
  (plus optional `victory`).
- A **head slot** that swaps per hero — the runtime supports
  `armature.skin.replaceSlotDisplay("head", newSprite)`. We feed in
  the existing 1050×1498 hero card crops (auto-cropped busts at
  512×512 already in `app/static/heroes/busts/`).
- An **optional weapon slot** for the ATK rig (sword vs gun vs laptop)
  so different ATK heroes don't all carry the same prop.

Future expansion: per-faction body recolors (HELPDESK orange, DEVOPS
green, etc.) via skin swap; alignment-fork outfits in Phase 3.5.

### 4. Asset pipeline

Where do rigs live + how do they ship?

- `app/static/battle-rigs/atk/` etc. — raw skeleton + atlas + textures.
- A registry mapping `template_code` → which rig + which head texture:
  `"ticket_gremlin" → {rig: "atk", head: "/heroes/busts/ticket_gremlin.png"}`.
- Could be a JSON file in `app/static/battle-rigs/registry.json`,
  read by the viewer at battle-load time.

## Work order (rough)

1. **Engine port** (decision 1) — ~2 days if option A.
2. **Stub registry** with the demo Mecha rig as the placeholder for all
   30-something heroes, just to prove the wiring through a real
   `Battle.id`. ~half-day.
3. **Author 3 production rigs** (decision 2) — ~3 days.
4. **Skin-swap** the heads via the registry — ~1 day.
5. **Polish pass** — sync particles + status tints + cinematics to the
   new rigs. Reuse the existing Phaser polish as a checklist. ~2 days.

Total: **~8 days to MVP** — matches the BATTLE_VISUALS_STACK.md estimate.

## What I can do without your input (small scaffolding wins)

- Build the registry JSON shape + a fake "all-heroes-render-as-mecha"
  placeholder pass so we can preview the integration.
- Write a stripped-down Pixi-based replay viewer prototype
  (`battle-pixi.html`) that consumes a real `Battle.id` and plays the
  mecha rig per unit, just to see how it feels in context.
- Document the runtime API + event-handler skeleton (which combat
  log entries map to which `armature.animation.play(...)` calls).

Tell me if you want any of those scaffolded next, or if you'd rather
sleep on the engine choice first.
