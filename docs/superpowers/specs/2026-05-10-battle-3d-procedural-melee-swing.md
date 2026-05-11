# Battle 3D — Procedural KayKit Melee Swing (v1.2)

**Date:** 2026-05-10
**Status:** Spec
**Context:** Replaces the `Throw` stand-in for KayKit melee attacks identified as a v1.1 follow-up in `TODO.md` and elaborated in `docs/superpowers/notes/2026-05-10-battle-3d-clip-names.md`.

## Problem

The 6 KayKit archetypes (knight, barbarian, mage, ranger, rogue, rogue_hooded) share `kaykit_general.glb` for animation clips. That rig ships no melee swing clip; `clipMap.ts` resolves `attack` to `Throw`. The visual reads as an unidiomatic over-the-shoulder toss when the hero should be swinging a sword.

## Goals

- A 400ms diagonal right-arm swing readable as a melee attack for all 6 KayKit archetypes.
- No new asset dependencies; built procedurally at runtime from `THREE.AnimationClip` primitives.
- Falls back to `Throw` automatically if bone discovery fails (no regression).
- Sub-100ms build cost per hero (negligible vs. GLB load time).

## Non-goals

- Druid melee — already has `Staff_Attack` and `Spell1`.
- Weapon-specific variants (slash vs. stab).
- Hit-sync pacing — current `animationDriver` plays attack-then-hit serially; no need to time the swing apex.
- Replacing this with a real authored clip — that path stays open in `clip-names.md` as v1.3.

## Approach

### 1. New module: `frontend/src/battle3d/proceduralClips.ts`

Exports:

```ts
buildKaykitMeleeSwing(root: THREE.Object3D): THREE.AnimationClip | null
```

- Walks `root` via `traverse`. Collects bones whose names case-insensitively match:
  - upper arm:  `/upper.?arm.*r$|^arm.*r$/i`
  - forearm:    `/fore.?arm.*r$|lower.?arm.*r$|elbow.*r$/i`
  - hand:       `/hand.*r$|wrist.*r$|fist.*r$/i`
- If any of the three categories has no match, return `null`.
- Build three `QuaternionKeyframeTrack`s, one per bone, with track name `<boneName>.quaternion`.
- Keyframe times: `[0.0, 0.12, 0.30, 0.40]` (rest → wind-up → swing apex → return).
- Pose deltas (Euler degrees, applied multiplicatively to bone's rest quaternion):
  - **upperarm_R** — rest, (-25° X, +15° Y, 0), (+55° X, -10° Y, 0), rest
  - **forearm_R** — rest, (+30° X, 0, 0), (-15° X, 0, 0), rest
  - **hand_R**    — rest, (0, +10° Z, 0), (0, -20° Z, 0), rest
- Clip name: `"MeleeSwing"`. Duration: `0.4`.

### 2. `heroLoader.ts` — splice in per-hero

For KayKit archetypes, after retrieving `kaykitClipsCache`:

1. Call `buildKaykitMeleeSwing(scene)`.
2. If non-null, return `animations: [meleeClip, ...sharedClips]` (per-instance array — clip is skeleton-bound to this scene).
3. If null, return shared clips unchanged.

The shared cache stays intact; per-hero merge happens on the returned array.

### 3. `clipMap.ts` — preference order

```diff
- attack: ["Throw"],
+ attack: ["MeleeSwing", "Throw"],
```

`resolveClip` already picks the first match present — heroes whose procedural build succeeded get `MeleeSwing`; failures fall through to `Throw`.

## Test plan (TDD)

### `proceduralClips.test.ts` (new)

1. **happy path** — fake `THREE.Object3D` with three bones `Hand_R`, `Forearm_R`, `UpperArm_R` ⇒ returns clip; `name === "MeleeSwing"`; `duration === 0.4`; exactly 3 tracks.
2. **bone naming variants** — `hand_r`, `LowerArm_R`, `RightArm` (uppercase, mixed, alternate words) ⇒ returns clip.
3. **missing forearm** — only `UpperArm_R` + `Hand_R` ⇒ returns `null`.
4. **empty scene** — `new THREE.Object3D()` ⇒ returns `null`.
5. **track names match bone names exactly** — track name prefix equals the bone's actual `.name`.

### `heroLoader.test.ts` (extend)

6. KayKit hero load — when `buildKaykitMeleeSwing` returns a clip, `animations[0].name === "MeleeSwing"`; subsequent entries are the shared clips.
7. Druid load — unchanged; no `MeleeSwing` prepended.

### `clipMap.test.ts` (extend)

8. `resolveClip("knight", "attack", ["MeleeSwing", "Throw"])` ⇒ `"MeleeSwing"`.
9. `resolveClip("knight", "attack", ["Throw"])` ⇒ `"Throw"` (procedural failed; fallback works).

### `animationDriver.test.ts` — no change required (clipMap layer absorbs the swap).

## Files touched

- `frontend/src/battle3d/proceduralClips.ts` — new (~80 lines)
- `frontend/src/battle3d/__tests__/proceduralClips.test.ts` — new (~80 lines)
- `frontend/src/battle3d/heroLoader.ts` — +5 lines
- `frontend/src/battle3d/__tests__/heroLoader.test.ts` — +1 test
- `frontend/src/battle3d/clipMap.ts` — 1-line change
- `frontend/src/battle3d/__tests__/clipMap.test.ts` — +1 test

## Risk + rollback

- **Bone names diverge from regex patterns.** Mitigation: `null` return + `Throw` fallback in `clipMap`. Worst case: visual unchanged from today.
- **Quaternion deltas read wrong.** Spec-level tuning; numbers may need a single tweak after eyeballing in browser. Adjustable in one file.
- **Clip plays additively wrong.** Three.js plays clips exclusively via `mixer.clipAction(clip).play()` — the existing driver already calls `rig.play(name)` which crossfades; procedural clip layers like any other.

Rollback: revert the 1-line change in `clipMap.ts` — `MeleeSwing` becomes unused; `Throw` resumes.

## Out of scope / follow-ups

- Procedural slash trail VFX.
- Per-archetype swing variants (barbarian could be a heavier overhead; mage probably keeps `Throw` as a "cast" gesture).
- Audio sting on swing apex.
