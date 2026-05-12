# 2026-05-12 — Quaternius RPG Characters rig migration

## Goal

Replace the shared KayKit `Throw`-fallback attack with real per-archetype melee/ranged clips by migrating the 6 Battle 3D hero archetypes to the **Quaternius RPG Characters** pack. Closes TODO.md line 176 ("Real KayKit melee attack clip") and partial-closes line 177 ("engineer archetype model").

## Why Quaternius

- **Chibi proportions** match KayKit Rig_Medium aesthetic (Druid already uses Quaternius Cleric — proves pipeline).
- **Per-class attack clips** (`Sword_Attack`, `Staff_Attack`, `Dagger_Attack`, `Bow_Shoot`, `Attack`) replace the procedural arm-swing fallback.
- **Full source available** — can re-export rigs from Blender if Three.js skinning issues surface.

## Asset → archetype map

| Battle3D archetype | Quaternius rig | Attack clip(s) | Idle / Run |
|---|---|---|---|
| `knight` | Warrior | `Sword_Attack`, `Sword_Attack2` | `Idle_Weapon`, `Run_Weapon` |
| `barbarian` | Warrior | `Sword_Attack`, `Sword_Attack2` | `Idle_Weapon`, `Run_Weapon` |
| `mage` | Wizard | `Staff_Attack`, `Spell1`, `Spell2` | `Idle_Weapon`, `Run_Weapon` |
| `rogue` | Rogue | `Dagger_Attack`, `Dagger_Attack2` | `Attacking_Idle`, `Run` |
| `rogue_hooded` | Rogue | `Dagger_Attack`, `Dagger_Attack2` | `Attacking_Idle`, `Run` |
| `ranger` | Ranger | `Bow_Shoot`, `Bow_Draw` | `Idle_Weapon`, `Run_Holding` |
| `druid` | Cleric *(already wired)* | `Staff_Attack`, `Spell1` | `Idle_Weapon`, `Run` |
| `engineer` *(remap)* | Monk | `Attack`, `Attack2` | `Idle_Attacking`, `Run` |

Source pack: `maynewmodels/drive-download-20260509T192326Z-3-001/glTF/` — six `.gltf` files with embedded base64 buffers + external PNG textures in `../Textures/`.

## Tasks

1. **Asset prep** — convert each `.gltf` + adjacent PNG textures to a single self-contained `.glb` via `gltf-pipeline -i X.gltf -o X.glb -b -d` (binary + Draco). Output to `frontend/public/battle-3d/heroes/{warrior,wizard,rogue,ranger,monk}.glb`. Cleric already present (`druid.glb`).
2. **Rig map** — no `app/rig_map.py` change (rig names stay the same per-template). Update `scripts/gen-archetype-map.py::RIG_TO_ARCHETYPE` only if introducing the `monk`/`engineer` line. Run `uv run python scripts/gen-archetype-map.py` to regenerate `archetypeMap.ts`.
3. **Loader** — point each archetype at its dedicated `.glb` in `battle3d/sceneLoader.ts` (or wherever `kaykit_general.glb` is referenced). Each Quaternius `.gltf` ships embedded clips, so no shared animation file needed for the migrated heroes.
4. **clipMap.ts** — split `KAYKIT_CLIPS` into per-archetype candidate sets per the table above. Keep `Throw` only as last-resort fallback (or drop entirely). Procedural arm-swing fallback in `proceduralClips.ts` becomes dead code for migrated archetypes — leave for graceful degradation.
5. **Verify** — `npm run dev`, run a battle, check:
   - Console: no "clip-missing" telemetry from `recordBattle3DMetric`.
   - Visual: hero swings sword / casts staff / draws bow instead of `Throw` flail.
6. **TODO.md** — strike line 176 (done), line 177 (Monk slots in for engineer).

## Risk / fallback

- **Skinning failure** — if any Quaternius rig collapses after Draco, re-export uncompressed (`-b` only) or open in Blender from `Blends/` subfolder and re-glTF-export.
- **Scale mismatch** — Quaternius RPG chibi proportions ≈ KayKit; if visibly off, apply uniform scale at the scene group level (not on the SkinnedMesh — see [[feedback-threejs-skinned-clone]]).
- **Bundle size** — six `.glb`s at ~500KB each Draco-compressed ≈ 3MB. Acceptable inside the lazy-loaded battle3d chunk.

## Out of scope

- Mid-battle wave-swap (TODO line 178).
- Three.js bundle split beyond existing lazy chunk (line 179).
- Monster pack migration — separate follow-up; Ultimate Monsters chibi pack is identified as the next gold mine.
