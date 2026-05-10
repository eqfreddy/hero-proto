# KayKit + Quaternius hero clip names (harvested 2026-05-10)

Source: `scripts/harvest-gltf-clips.mjs` parsing GLB JSON chunk.

## barbarian
clips (0):

## druid
clips (11):
  - Death
  - Idle
  - Idle_Weapon
  - PickUp
  - Punch
  - RecieveHit
  - RecieveHit_Attacking
  - Run
  - Spell1
  - Staff_Attack
  - Walk

## knight
clips (0):

## mage
clips (0):

## ranger
clips (0):

## rogue
clips (0):

## rogue_hooded
clips (0):

## KayKit shared rig animations

KayKit ships character meshes (`Knight.glb`, `Barbarian.glb`, `Mage.glb`, `Ranger.glb`, `Rogue.glb`, `Rogue_Hooded.glb`) **without** embedded animations. All animations live in shared rig files under `maynewmodels/KayKit_Adventurers_2.0_FREE/.../Animations/gltf/Rig_Medium/`:

### Rig_Medium_General.glb (15 clips)
  - Death_A
  - Death_A_Pose
  - Death_B
  - Death_B_Pose
  - Hit_A
  - Hit_B
  - Idle_A
  - Idle_B
  - Interact
  - PickUp
  - Spawn_Air
  - Spawn_Ground
  - T-Pose
  - Throw
  - Use_Item

### Rig_Medium_MovementBasic.glb (11 clips)
  - Jump_Full_Long
  - Jump_Full_Short
  - Jump_Idle
  - Jump_Land
  - Jump_Start
  - Running_A
  - Running_B
  - T-Pose
  - Walking_A
  - Walking_B
  - Walking_C

The 6 KayKit hero archetypes (knight/barbarian/mage/ranger/rogue/rogue_hooded) all share the same Rig_Medium skeleton, so animations from these two rig files can be applied to any of them via Three.js `AnimationClip` retargeting on a common bone hierarchy.

## Concerns

- **KayKit hero .glb files contain zero embedded animations.** Task 2 must load `Rig_Medium_General.glb` + `Rig_Medium_MovementBasic.glb` once at boot and retarget those clips onto each KayKit hero's skeleton. The 6 character GLBs in `frontend/public/battle-3d/heroes/` carry mesh + skeleton only.
- **No dedicated attack clip in KayKit rigs.** Closest matches: `Throw` (ranged toss), `Interact`, `Use_Item`, `PickUp`. The `clipMap` resolver should pick `Throw` as the attack default for KayKit archetypes, with per-archetype overrides if a better fit exists. Druid has explicit `Staff_Attack` / `Punch` / `Spell1` so it can map cleanly.
- **No `hit` / damage-react clip on Druid.** Druid has `RecieveHit` (sic) and `RecieveHit_Attacking` — note the misspelling, it's the canonical name in the source asset, not a typo we should fix.
- **Naming asymmetry.** KayKit uses `_A`/`_B` variants (Idle_A, Idle_B, Death_A, Hit_A) while Druid uses singular names (Idle, Death). The `clipMap` must normalise across both conventions per archetype.
- **Two rig animation GLBs add ~payload** (not yet copied to `frontend/public/battle-3d/`). Decide in Task 2 whether to:
  1. Copy both `Rig_Medium_*.glb` to `frontend/public/battle-3d/animations/` and load once shared, or
  2. Bake just the 4 canonical clips (idle/attack/hit/die) into a single `kaykit_clips.glb`.
  Option 2 is leaner. Required clips per canonical slot:
  - idle → `Idle_A`
  - attack → `Throw` (or per-archetype: knight/barbarian → `Throw`; mage → `Throw`; rogue → `Throw`; ranger → `Throw`)
  - hit → `Hit_A`
  - die → `Death_A`
