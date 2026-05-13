# Debug: Post-Battle Return Button Goes Nowhere

**Date:** 2026-05-12

## Root Cause

`BattlePlayRoute` is mounted under the `/battle` path tree (outside the `/app` Shell), but the `onClose` handler passed to `BattleHUD` calls `navigate('/app/stages')`. That path exists in the router and is valid — so navigation itself is not the problem. The real blocker is the `useEffect` at line 22–26 of `BattlePlayRoute.tsx`: the moment `done` becomes `true` **and** `state.battle_id` is set, the effect fires `window.location.replace(...)` which performs a hard redirect to a static HTML page (`/app/static/battle-arena.html?battle_id=...`). That page is a standalone replay viewer with no React router context, so `navigate('/app/stages')` from inside `BattleHUD` runs but the browser is simultaneously being replaced by `window.location.replace`. The hard replace wins, lands on the static page, and any subsequent button click on the "Continue" button — which is rendered in the React tree that is about to be torn down — either fires into a dead router or the user sees the static replay page with no Continue button at all. The button appears to do nothing.

## Exact Location

`frontend/src/routes/battle/BattlePlayRoute.tsx`, lines 22–26:

```tsx
useEffect(() => {
  if (done && state?.battle_id) {
    window.location.replace(`/app/static/battle-arena.html?battle_id=${state.battle_id}`)
  }
}, [done, state?.battle_id])
```

This effect fires unconditionally as soon as the battle ends, racing with (and overriding) the `onClose` navigate call wired at line 77.

## Proposed Fix

Remove the auto-redirect effect entirely, or gate it behind an explicit user action (e.g. a "Watch Replay" button). The `onClose` path (`/app/stages`) is correct and the route exists. The Continue button will work as soon as nothing hijacks navigation first:

```tsx
// DELETE or comment out these lines (22-26):
// useEffect(() => {
//   if (done && state?.battle_id) {
//     window.location.replace(`/app/static/battle-arena.html?battle_id=${state.battle_id}`)
//   }
// }, [done, state?.battle_id])
```

If replay access is still needed, add a secondary "Watch Replay" button inside the `BattleHUD` rewards overlay that the user can optionally click, keeping `onClose` → `navigate('/app/stages')` as the primary action.

## Test Gap

`BattleHUD.test.tsx` tests that the rewards overlay renders and that `onClose` is wired to the button, but never asserts that `onClose` actually causes navigation. No test covers the `window.location.replace` effect in `BattlePlayRoute` at all — a test mocking `window.location.replace` and asserting it is NOT called on `done=true` would catch this regression.

## Confidence

**High.** The `window.location.replace` call is unconditional on `done && battle_id`, executes synchronously with the effect flush, and hard-navigates away from the React app before the user can interact with the Continue button.
