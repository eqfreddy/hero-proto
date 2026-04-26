# DragonBones — feasibility demo

This directory ships **two official DragonBones samples** + the Pixi 4.6 +
DragonBones 5.7 runtime so you can evaluate **Plan B** from
`docs/BATTLE_VISUALS_STACK.md` without leaving your dev environment.

## How to view

Either:

- Click the `🐉 DragonBones demo` pill at the top of the **Stages** tab in
  the running app, or
- Open `http://<host>/app/static/dragonbones-demo/` directly.

The demo renders inside an 800×500 canvas — the same dimensions as
`/app/battle-phaser.html`, so the visual scale matches what would land
in production.

## What's in here

| File | Purpose | Source |
|---|---|---|
| `libs/pixi.js` | Pixi 4.6.0 (1.47 MB) | DragonBonesJS repo, MIT |
| `libs/dragonBones.js` | DragonBones 5.7 Pixi runtime (728 KB) | DragonBonesJS repo, MIT |
| `mecha_1004d/` | The flagship sample — full action set: idle / walk / hit / death / attack_01 / skill_01..05 / victory | DragonBonesJS repo, Apache-2.0 |
| `mecha_1004d_show/` | Single-pose beauty render of the same character | DragonBonesJS repo, Apache-2.0 |
| `index.html` | Self-contained demo page wired to both samples + animation buttons + speed slider | hero-proto |

Total weight: ~3.3 MB. Repo cost is one-time; production rigs would replace
these with our own characters.

## Maps onto the combat resolver

| DragonBones animation | Combat event |
|---|---|
| `idle` | between turns / waiting |
| `walk` | entrance / retreat |
| `attack_01` | `DAMAGE` with `via=BASIC` |
| `skill_01` | SPECIAL type DAMAGE |
| `skill_03` | SPECIAL type AOE_DAMAGE |
| `skill_04` | SPECIAL type HEAL / AOE_HEAL |
| `skill_05` | SPECIAL type BUFF / AOE_BUFF |
| `hit` | incoming `DAMAGE` |
| `death` | `DEATH` |
| `victory` | end-of-battle WIN |

The replay viewer's existing event log shape already carries everything
needed to drive these — no resolver changes needed for Plan B.

## Why Pixi 4.6 here, when Phaser is our production stack

DragonBones ships a Pixi runtime, an Egret runtime, and a Cocos runtime
out of the box. Phaser support comes from a community plugin
(`raksa/phaser-dragonbones`). Pixi 4.6 is the easiest "just works" path
for a feasibility demo — no Phaser plugin install, no version pin
hunting.

In production you'd either:

1. Switch the battle viewer from Phaser to Pixi 8.x (Pixi 8 has a maintained
   DragonBones runtime via `pixi-dragonbones-runtime`), **or**
2. Keep Phaser and install the `raksa/phaser-dragonbones` plugin, **or**
3. Run DragonBones inside Phaser via the embedded Pixi instance Phaser
   already uses internally (advanced — would need plugin help).

Path 1 is cleanest if we're starting fresh; path 2 is least disruptive
since the Phaser viewer already works.

## Licensing

The runtime + sample data are licensed under the upstream Apache-2.0 /
MIT terms from the official `DragonBones/DragonBonesJS` repository. They
ship in this repo only as a feasibility demo and would be replaced (or
trimmed) in production.
