# KayKit + Quaternius hero clip names (harvested 2026-05-10)

Source: `scripts/harvest-gltf-clips.mjs` parsing GLB JSON chunk. Scans both
`frontend/public/battle-3d/heroes/` and `frontend/public/battle-3d/animations/`.

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

## kaykit_general
clips (15):
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

## kaykit_movement
clips (11):
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

## Runtime pattern for KayKit heroes

KayKit heroes share a single skeleton. Their `.glb` files contain mesh + skeleton only — no AnimationClips. AnimationClips live in `kaykit_general.glb` and `kaykit_movement.glb`.

At load time:
1. Load each KayKit hero `.glb` via GLTFLoader → get `gltf.scene` (mesh + bones).
2. Load `kaykit_general.glb` once and cache → take `gltf.animations` (the AnimationClip array).
3. Construct `new THREE.AnimationMixer(heroScene)` and call `mixer.clipAction(clip)` with the shared clips. Three.js retargets the clip to the hero's skeleton automatically because they share track-name structure.

The Druid (Quaternius `Cleric.gltf`) is the exception — its clips live in the model file itself.

The clipMap resolver in Task 2 must therefore know: which archetype uses shared clips (KayKit set) vs. embedded clips (Druid). The simplest API: `loadClipsFor(archetype)` returns the AnimationClip[] array regardless of where they actually came from.

## Archetype clip resolution

Candidate ordering per canonical slot. Resolver picks the first clip name that exists on the loaded AnimationClip[] for the archetype's source.

### KayKit archetypes (knight, barbarian, mage, ranger, rogue, rogue_hooded)
Source: `kaykit_general.glb` (shared rig).

| slot   | candidates (in order)        |
|--------|------------------------------|
| idle   | `Idle_A`, `Idle_B`           |
| attack | `Throw`                      |
| hit    | `Hit_A`, `Hit_B`             |
| die    | `Death_A`, `Death_B`         |

> v1.1 follow-up: KayKit ships no melee attack clip in the General rig. `Throw` is the closest action and is used as the v1 attack stand-in. Source a real melee swing clip (or author one) before v1.1.
>
> **Investigated 2026-05-10:** Searched all asset folders (incl. 11 new drive-downloads dropped that day) for a melee clip retargetable to the KayKit Medium rig. Findings:
> - KayKit FREE pack ships only General + MovementBasic rigs. No KayKit premium melee pack appears to be available.
> - `drive-download-20260510T161025Z-3-001` ships a `KnightCharacter.fbx` with its own rig + weapons — incompatible with KayKit chibi bones, would not retarget.
> - Other free packs (Quaternius RPG, Ultimate Animated Character) use different skeletons.
>
> **Recommended paths for v1.2:**
> 1. **Procedural melee in Three.js** — write a 400ms runtime `AnimationClip` that rotates the right-arm bones in a diagonal swing arc. Requires knowing KayKit's bone hierarchy (likely `Hand_R`, `Forearm_R`, `UpperArm_R`). Plays additively over the idle clip. ~80 lines.
> 2. **Custom Blender export** — open `Rig_Medium_General.glb` in Blender, author a 30-frame melee swing, append to the rig's animation list, re-export. Most "correct" but requires Blender.
> 3. **Try other in-pack candidates** — `Interact`, `Use_Item`, `PickUp` may look more melee-like than `Throw` on a swinging fighter. Easy to test: re-order the `attack` candidates in `clipMap.ts::KAYKIT_CLIPS`. No code change beyond that array.
>
> Until then, `Throw` remains the attack stand-in. The visual is unidiomatic but functional — combat still reads.

### Druid (Quaternius Cleric)
Source: `druid.glb` (embedded clips).

| slot   | candidates (in order)                  |
|--------|----------------------------------------|
| idle   | `Idle`, `Idle_Weapon`                  |
| attack | `Staff_Attack`, `Spell1`, `Punch`      |
| hit    | `RecieveHit`                           |
| die    | `Death`                                |

> Note: `RecieveHit` misspelling is preserved — it is the canonical name in the source asset.

## Concerns

- **KayKit hero meshes carry zero embedded animations.** Confirmed: all 6 KayKit `.glb` files (knight, barbarian, mage, ranger, rogue, rogue_hooded) report 0 clips. Animations are now bundled as two shared `.glb` rigs in `frontend/public/battle-3d/animations/` (`kaykit_general.glb`, `kaykit_movement.glb`, both Draco-compressed).
- **Runtime must distinguish shared-clip archetypes vs. embedded-clip archetypes.** KayKit set → load shared rig once at boot, cache, reuse `AnimationClip[]` across all 6 hero meshes via `AnimationMixer` retargeting. Druid → use `gltf.animations` from its own file. The `loadClipsFor(archetype)` API hides this split from callers.
- **No dedicated melee attack clip in KayKit General rig.** Slot resolution falls back to `Throw`. Flagged for v1.1.
- **No `hit` / damage-react on Druid.** `RecieveHit` (sic) is canonical — preserve the misspelling in clipMap.
- **Naming asymmetry across sources.** KayKit uses `_A`/`_B` variants; Druid uses singular names. The candidate-order lists above absorb this; clipMap consumes them as-is.
- **Two rig animation GLBs add ~1.5 MB payload** (`kaykit_general.glb` ~825 KB, `kaykit_movement.glb` ~687 KB after Draco). Loaded once, shared across 6 archetypes — cheaper than baking per-archetype clip files.
