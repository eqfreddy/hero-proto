# Debug Report: "KayKit models" regression — 2026-05-12

## Summary

**Not a regression.** The migration is complete and correctly deployed. The
Quaternius files are live on disk, in git, and compiled into the current SPA
bundle. The user's perception of "old kitkay models" is most likely a browser
cache serving a stale bundle.

---

## Evidence

### Assets — Quaternius sizes confirmed everywhere

| File | Size | Timestamp |
|---|---|---|
| `frontend/public/battle-3d/heroes/knight.glb` | 1,763,304 B | May 12 03:54 |
| `frontend/public/battle-3d/heroes/barbarian.glb` | 1,763,304 B | May 12 03:54 |
| `frontend/public/battle-3d/heroes/mage.glb` | 1,933,512 B | May 12 03:54 |
| `frontend/public/battle-3d/heroes/rogue.glb` | 1,561,584 B | May 12 03:54 |
| `frontend/public/battle-3d/heroes/ranger.glb` | 1,735,720 B | May 12 03:54 |
| `app/static/spa/battle-3d/heroes/*.glb` | Same sizes, May 12 21:36 |

KayKit originals were 344–487 KB. All on-disk files are 1.4–1.9 MB. The old
shared rig directory `frontend/public/battle-3d/animations/` does not exist
(deleted in commit `146e62f`).

### Code — migration path correct

- `heroLoader.ts` loads `${archetype}.glb` directly, no shared-rig branch.
- `clipMap.ts` maps per-archetype Quaternius clip names (`Sword_Attack`,
  `Staff_Attack`, `Dagger_Attack`, `Bow_Shoot`). No `kaykit_general` or
  `MeleeSwing` references remain.
- `animationDriver.ts` calls `resolveClip()` only — no procedural fallback.
- `proceduralClips.ts` deleted in `146e62f`.

### Bundle — built after migration, correct clip names embedded

`app/static/spa/assets/Battle3DScene-yk5fRkrs.js` (630 KB, built 2026-05-12
21:36):

```
Sword_Attack  x4
Dagger_Attack x4
Staff_Attack  x2
Bow_Shoot     x1
```

No `kaykit_general`, no `proceduralClip`, no `MeleeSwing`.

---

## Root Cause

**Browser cache.** The SPA uses a service worker (`sw.js`, `workbox-*.js`). A
user visiting before the 21:36 rebuild has the old bundle (and old, small GLBs)
cached by the service worker. The SW will not serve the new assets until it
re-fetches and installs the updated `sw.js`.

The GLB filenames did not change (e.g., `knight.glb`), so the browser cache
has no URL-based reason to invalidate them even after the SW updates.

---

## Proposed Fix

1. **Immediate (user-facing):** Hard-reload with cache clear (`Ctrl+Shift+R` /
   `Shift+Reload`), or open DevTools → Application → Service Workers →
   "Unregister", then reload.

2. **Permanent fix — cache-bust GLB URLs in heroLoader:** Append a build-time
   version hash to the GLB URL so SW/CDN caches are invalidated on deploy:

   ```ts
   // heroLoader.ts
   const HERO_VERSION = "v20260512"; // bump each time GLBs change
   p = loadGLTF(`${HERO_BASE}/${archetype}.glb?v=${HERO_VERSION}`);
   ```

   Or inject `import.meta.env.VITE_ASSET_VERSION` from `vite.config.ts` using
   `define` + `Date.now()` at build time for automatic busting.

3. **Workbox asset manifest:** Add the `battle-3d/heroes/*.glb` pattern to the
   Vite PWA plugin's `globPatterns` so the service worker revision-hashes them
   and auto-invalidates on deploy.

---

## Confidence

**High (95%).** Code, assets, and bundle all confirm the migration is deployed
correctly. The only mechanism that can serve the old models to a specific user
is a stale service worker or browser cache.
