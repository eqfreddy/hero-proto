# Battle 3D Viewer (Interactive Mode) v1 — Design Spec

**Goal:** Replace the empty "BATTLE" watermark in `BattlePlayRoute` (interactive-mode battles) with a Three.js scene rendering KayKit GLTF heroes/enemies on an Asset Forge diorama backdrop. Existing `BattleHUD` overlay stays. Instant-replay path (`BattleReplayRoute`) keeps using `battle-arena.html` — no change.

**Architecture:** New `Battle3DScene.tsx` React component mounts a Three.js WebGL canvas. Loads KayKit hero archetype GLTFs (cached per-session) + Asset Forge diorama for the stage's theme. Reads interactive-session state from `BattlePlayRoute` props and drives per-unit AnimationMixers via a small `animationDriver` module. Combat-log events trigger attack/hit/die animations + material flash + damage-number floats.

**Tech Stack:** Three.js + GLTFLoader (Draco-compressed). React 18. No backend changes — uses existing `/battles/interactive/*` endpoints.

**Out of scope (v2+):** Special-ability distinct animations, status-effect particle systems, cinematic camera moves, Three.js applied to instant-replay path, ragdoll physics, interactive diorama elements.

---

## 1. Component structure

```
frontend/src/battle3d/
├── Battle3DScene.tsx       Main canvas + scene setup
├── heroLoader.ts           GLTF cache for hero archetypes
├── dioramaLoader.ts        GLTF cache + positioning for stage themes
├── animationDriver.ts      Maps combat events → AnimationAction triggers
└── constants.ts            Camera positions, lighting, slot positions

frontend/public/battle-3d/
├── heroes/
│   ├── knight.glb          ~300KB Draco
│   ├── barbarian.glb
│   ├── mage.glb
│   ├── rogue.glb
│   ├── rogue_hooded.glb
│   ├── ranger.glb
│   ├── druid.glb
│   └── engineer.glb
└── props/
    ├── server-closet.glb   ~800KB Draco — composited Asset Forge scene
    ├── cubicle-farm.glb
    ├── exec-floor.glb
    ├── data-center.glb
    └── break-room.glb
```

**Total payload target:** ≤20 MB compressed. Lazy-loaded on `BattlePlayRoute` mount.

---

## 2. Mount, render, dismount

`Battle3DScene` props:
```typescript
interface Battle3DSceneProps {
  teamA: InteractiveUnit[];   // 3 ally units (left side)
  teamB: InteractiveUnit[];   // 3 enemy units (right side)
  stageCode: string;           // For diorama selection
  pendingActorUid: string | null;   // Highlight current actor
  lastEvent: CombatLogEvent | null; // Drives attack/hit animations
  done: boolean;               // Triggers wave-clear or victory pose
}
```

Mount sequence:
1. Detect WebGL support → if missing, render placeholder div + log warning.
2. Initialize Three.js: `WebGLRenderer`, `Scene`, `PerspectiveCamera` (3-quarter angle, fixed), `AmbientLight` (intensity 0.6) + `DirectionalLight` (intensity 0.8 from upper-left).
3. Load diorama GLTF for `stageCode` via `dioramaLoader` — fallback to `server-closet` on miss.
4. Load hero GLTFs for both teams via `heroLoader` (cached). Position teamA at slots `[-2, 0, 0]`, `[-2, 0, -1.5]`, `[-2, 0, 1.5]`. Position teamB mirrored on x.
5. Per unit: clone scene, attach `AnimationMixer`, start `idle` clip.
6. Begin animation frame loop.

Render-loop steps per frame:
- Update each AnimationMixer with delta time.
- If `pendingActorUid` set, glow the corresponding unit (rim light material override).
- Process `lastEvent` once per change (compare to previous):
  - `DAMAGE` event with attacker uid → fire attacker `attack` clip; on impact frame, fire defender `hit` clip + flash white + spawn floating damage number above defender.
  - `DEATH` event → fire `die` clip on the dying unit; afterwards lock dead pose + opacity 0.4.
  - `SPECIAL` event → fire attacker `attack` clip + emoji particle overlay (DOM, not Three.js).

Dismount:
- Cancel animation frame.
- Dispose all geometries, materials, textures.
- Renderer `dispose()`.

---

## 3. Hero archetype mapping

New constant in `app/rig_map.py` (or sibling module — keep close to existing `RIG_FOR_TEMPLATE`):

```python
HERO_3D_ARCHETYPE: dict[str, str] = {
    # Tank / TANK role → knight
    "the_sysadmin":      "knight",
    "frontline_l1_tech": "knight",
    "oncall_warrior":    "knight",
    # ... (full mapping during implementation)
}
DEFAULT_3D_ARCHETYPE = "knight"
```

Surfaced via `/heroes/{id}` and `/me` responses (existing fields can be extended, or a new `archetype_3d` field added). Frontend looks up by template_code.

**Faction tinting:** When loading a hero GLTF, override `MeshStandardMaterial.color` with a faction-derived hue:
- EXILE → no tint (neutral)
- RESISTANCE → tint blue (`#4eb8ff`, 15% blend)
- CORP_GREED → tint gold (`#ffd166`, 15% blend)

This gives visual differentiation between heroes that share an archetype.

---

## 4. Stage diorama mapping

New constant in `app/static/battle-arena.html`'s sibling — preferably moved to a Python-served map for consistency with the existing `STAGE_CODE_TO_BG`. For v1, hardcode in `frontend/src/battle3d/dioramaLoader.ts`:

```typescript
const STAGE_3D_THEME: Record<string, string> = {
  "tutorial_first_ticket":  "cubicle-farm",
  "stage_1_2":              "cubicle-farm",
  "server_room_intro":      "server-closet",
  "boss_office":            "exec-floor",
  // ... 26 stage codes mapped to 5 themes (HARD/NIGHTMARE/LEGENDARY tiers
  // share the NORMAL stage's theme; tier signals via lighting tint, see below)
};
const DEFAULT_THEME = "server-closet";
```

Tier visual differentiation (low-cost): adjust DirectionalLight color/intensity by `stage.difficulty_tier`:
- NORMAL → warm white (default)
- HARD → cool blue tint
- NIGHTMARE → red-orange tint, intensity 1.1
- LEGENDARY → flickering between colors (subtle)

---

## 5. Animation cue table

| Combat event | Trigger | Animation clip(s) |
|---|---|---|
| `pending` (player's turn) | `pendingActorUid` set | actor: idle (already looping) + rim glow |
| `act` request fires server-side | `lastEvent.type === "DAMAGE"` arrives | attacker: `attack` (1.0× speed); on ~50% clip progress, defender: `hit` (1.0×) + material flash white 200ms + damage number float-up |
| `DEATH` | `lastEvent.type === "DEATH"` | victim: `die` (1.0×); after clip, hold last frame at opacity 0.4 |
| `SPECIAL` | `lastEvent.type === "SPECIAL"` | attacker: `attack` (1.0×, no special clip distinction) + DOM emoji particle (existing battle-arena.html pattern) |
| Wave end (all enemies dead) | `team_b` all dead | enemies fade to opacity 0 over 800ms; new wave units fade in over 800ms |
| Victory | `done && playerSurvived` | all heroes: idle continues + camera nudges in slightly |
| Defeat | `done && !playerSurvived` | all heroes: stuck at last frame, scene desaturates |

---

## 6. Performance constraints

- **Bundle target:** ≤20 MB compressed (Draco) for all hero + diorama GLTFs combined.
- **FPS target:** 30 minimum on iPhone 12 / Pixel 5 with 6 units rendered.
- **Triangle budget:** ≤10k triangles per scene (KayKit chars are ~1-2k each, props ~3-5k).
- **Texture budget:** Keep all textures ≤1024×1024.
- **Shadows:** None in v1 (baked into ambient occlusion textures, or skipped entirely).
- **Lighting:** 1 ambient + 1 directional. No shadow maps. No HDR.
- **Code-split:** Three.js + battle3d module is lazy-loaded only on `/battle/{id}/play`. The instant-battle path (which redirects straight to `battle-arena.html`) never pays the cost.

---

## 7. Error handling

| Failure | Fallback |
|---|---|
| WebGL unsupported | Render existing "BATTLE" watermark; battle still playable via `BattleHUD` |
| Hero GLTF 404 | Render a labeled placeholder cube; log warning |
| Diorama GLTF 404 | Use `server-closet` (default theme) |
| Unknown hero archetype | Use `DEFAULT_3D_ARCHETYPE = "knight"`; log warning |
| Unknown stage theme | Use `server-closet`; log warning |
| Animation clip missing | Idle loop only; log warning |
| Out-of-memory on mobile | (Browser will close tab; nothing to handle proactively in v1) |

---

## 8. Integration with `BattlePlayRoute`

Modify `frontend/src/routes/battle/BattlePlayRoute.tsx` (currently 68 lines):
- Replace the watermark `<div>BATTLE</div>` (line 40) with `<Battle3DScene>` reading the same state already in scope.
- Pass: `teamA={state.team_a}`, `teamB={state.team_b}`, `stageCode={state.stage_code}`, `pendingActorUid={pending?.actor_uid ?? null}`, `lastEvent={state.last_event ?? null}`, `done={done}`.
- Wrap in error boundary so a Three.js crash doesn't blow up the HUD.
- Keep `BattleHUD` overlay above (unchanged).

`state.stage_code` and `state.last_event` may not yet exist on `InteractiveStateOut` — backend may need to extend the response. Check during implementation; add a backend field if needed.

---

## 9. Asset preparation pipeline

One-time prep before any code lands:

1. Pull KayKit `.glb` files from `maynewmodels/KayKit_Adventurers_2.0_FREE/`.
2. Run each through `gltf-pipeline` (npm) with `--draco`.
3. Verify each has the 4 required clips: `idle`, `attack`, `hit`, `die`. Some KayKit chars use slightly different clip names — rename if needed via Blender or a re-export.
4. Save to `frontend/public/battle-3d/heroes/`.
5. For dioramas: open Asset Forge → compose 5 themes → export each as `.glb` → run through `gltf-pipeline --draco` → save to `frontend/public/battle-3d/props/`.

This prep is documented in the implementation plan as Task 1 — needs to happen before any React/Three.js code can render anything.

---

## 10. Testing

- **Unit:** `animationDriver.ts` — given a combat-log event sequence, fires the right clips on the right units.
- **Component:** `Battle3DScene` mounts without crashing given stub teams + a stub diorama (use a tiny GLTF fixture).
- **Build:** `npm run build` produces a separate Three.js chunk that doesn't bloat the main bundle (verify with `vite build --analyze` or equivalent).
- **Manual QA:** Run a real interactive battle in dev. Verify: heroes render, attack animations fire on target, hit-flash visible, death pose locks, scene cleans up on navigation away. Test in Chrome devtools mobile emulation (iPhone 12 / Pixel 5 viewport + CPU throttle).
- **Performance:** Lighthouse FPS profile during a battle. Confirm ≥30 FPS sustained.

---

## 11. Out of scope (v2+ deferrals)

- Distinct `special` animation clip per character (currently SPECIAL reuses `attack`)
- Status-effect particle systems (poison cloud, burn embers, freeze frost)
- Cinematic camera moves (zoom on attacker, pan to target)
- Three.js viewer for instant-replay battles (battle-arena.html stays)
- Ragdoll death physics (opacity fade + last-frame-hold in v1)
- Per-stage unique diorama (5 themes shared across 26 stages × 4 tiers)
- Hero-specific accessories / outfit modular swaps (KayKit supports modular but v1 uses single-piece archetype models)
- Mobile-specific perf modes (low-poly variants, dropped frame budget)

---

## 12. Summary

| Surface | Type | New |
|---|---|---|
| `frontend/public/battle-3d/heroes/*.glb` | Static assets (5–8 files, ~2-4MB total Draco) | ✓ |
| `frontend/public/battle-3d/props/*.glb` | Static assets (5 files, ~3-5MB total Draco) | ✓ |
| `frontend/src/battle3d/Battle3DScene.tsx` | React component | ✓ |
| `frontend/src/battle3d/heroLoader.ts` | GLTF cache | ✓ |
| `frontend/src/battle3d/dioramaLoader.ts` | GLTF cache + theme map | ✓ |
| `frontend/src/battle3d/animationDriver.ts` | Combat-event → animation cue | ✓ |
| `frontend/src/battle3d/constants.ts` | Camera, lighting, slot positions | ✓ |
| `BattlePlayRoute.tsx` modification | Mount Battle3DScene | Modify |
| `app/rig_map.py` `HERO_3D_ARCHETYPE` dict | Backend mapping (~41 entries) | ✓ |
| `/me` or `/heroes/{id}` extends to surface archetype_3d | Backend (light) | Modify (if needed) |
| `InteractiveStateOut` extends with stage_code + last_event (if missing) | Backend (light) | Modify (if needed) |
| Three.js dependency added to `frontend/package.json` | npm install | ✓ |
