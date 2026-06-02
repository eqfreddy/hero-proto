# SUDO In-App Onboarding Tour Design

**Date:** 2026-06-02
**Status:** Approved (design), ready for implementation plan.
**Scope:** Player-facing first-session onboarding — the deferred in-app half of SUDO (CLI half shipped 2026-05-31). Frontend only.

## Purpose

A brand-new player lands in the SPA (Shell → Lobby/Home) with no guided introduction to the core loop. This adds a **first-session, skippable, SUDO-guided spotlight tour** of the 3-step core loop (Summon → Team → Battle), reusing the existing `CoachMark` spotlight technique. SUDO — the deadpan helpdesk daemon from the CLI walkthrough — is the guide, rendered as a styled CSS avatar in a soft card.

**Psychology / Rule #1:** Autonomy — Skip on every step, never traps the UI. Competence — teaches the loop concisely (3 beats, no overload). Relatedness — SUDO's personality. No dark patterns; the tour never gates progress.

## Architecture

Frontend-only. Four small units + two light edits to existing files.

1. **`frontend/src/components/SudoAvatar.tsx` (+ `SudoAvatar.css`)** — presentational. A CSS/SVG daemon face (soft rounded look, deadpan eyes). One friendly-deadpan face for v1. Prop: `size?: number` (default 56). No state, no deps. Reusable (could later replace ASCII elsewhere).

2. **`frontend/src/onboarding/onboardingSteps.ts`** — the step data. Exported `ONBOARDING_STEPS: OnboardingStep[]` where:
   ```ts
   interface OnboardingStep { tourTarget: string | null; title: string; body: string }
   ```
   Three steps (copy in SUDO's register, a touch warmer):
   - `{ tourTarget: 'heroes', title: 'Step 1 — Recruit', body: 'Summon your first recruits. They live under Heroes. Try not to whiff.' }`
   - `{ tourTarget: 'heroes', title: 'Step 2 — Build', body: 'Form a squad from what you pulled. Same place. Drag the good ones in.' }`
   - `{ tourTarget: 'battle', title: 'Step 3 — Deploy', body: 'Throw them at a stage. This is the part that matters. Permission granted.' }`
   Steps 1 & 2 intentionally share the Heroes hub — recruiting and team-building both live there.

3. **`frontend/src/onboarding/useOnboarding.ts`** — the gate + persistence hook. Pure logic, testable.
   ```ts
   const KEY = 'heroproto_onboarding_seen'
   function hasSeenOnboarding(): boolean        // localStorage read, try/catch
   function markOnboardingSeen(): void
   export function replayOnboarding(): void     // clears KEY (for the Account "Replay intro" link)
   export function useShouldOnboard(accountLevel: number | undefined): boolean
   //   true iff accountLevel === 1 && !hasSeenOnboarding()
   ```

4. **`frontend/src/components/SudoOnboarding.tsx` (+ `SudoOnboarding.css`)** — the tour controller. Self-contained; reads `useMe()` for `account_level`, gates via `useShouldOnboard`. When active:
   - Dimmed full-screen backdrop (`position: fixed; inset: 0; z-index` above app, below toasts).
   - Spotlight ring around the current step's target, located by `document.querySelector('[data-tour="${tourTarget}"]')` + `getBoundingClientRect()` (same ring style as `CoachMark`). If `tourTarget` is null or the element isn't found, skip the ring and center the SUDO card.
   - A SUDO card (`SudoAvatar` + `title` + `body` + step dots + **Next**/**Skip tour** buttons). Final step's primary button reads "Got it".
   - `Next` advances the step index; reaching the end (or "Got it") calls `markOnboardingSeen()` + hides. `Skip tour` does the same immediately.
   - Recomputes the target rect on step change and on window `resize` (listener added/removed in an effect).
   - Renders nothing when not onboarding.

**Light edits to existing files:**
- **`frontend/src/components/Layout/PlayNav.tsx`** — add `data-tour="heroes"` to the Heroes `NavLink` and `data-tour="battle"` to the Battle `NavLink`. (Match on the slot's `label` or `path`; attribute only, no behavior change.)
- **`frontend/src/components/Layout/Shell.tsx`** — mount `<SudoOnboarding />` once (alongside `PlayNav`, inside the authed shell).
- **`frontend/src/routes/Account.tsx`** (or the existing account/settings route) — add a low-key "Replay intro" button calling `replayOnboarding()` then navigating to `/app/me` (or reloading the shell) so the tour re-fires. (If no Account route exists at that exact path, place it on the settings surface that does.)

## Data flow

`Shell` mounts `SudoOnboarding` → it calls `useMe()` (account_level) + `useShouldOnboard` → if true, renders backdrop + spotlight (querying `[data-tour]` on the live PlayNav) + SUDO card → user taps Next×3 or Skip → `markOnboardingSeen()` writes localStorage → component returns null thereafter. No network, no backend.

## Error handling / edge cases

- `localStorage` access wrapped in try/catch (private mode / disabled) → treated as "not seen" but writes are best-effort (matches `CoachMark`).
- Target element missing (e.g., PlayNav not yet mounted, or a layout without the bottom nav) → that step centers the card with no ring; the tour still completes.
- `account_level` undefined (me not loaded yet) → `useShouldOnboard` returns false until it loads; the tour appears once `/me` resolves for a level-1 account.
- Window resize while open → spotlight rect recomputed.

## Testing (vitest, jsdom — run via `bun run test`)

- **`useOnboarding.test.ts`**: `useShouldOnboard(1)` true when unseen, false after `markOnboardingSeen()`; false for `accountLevel > 1`; false for `undefined`; `replayOnboarding()` re-enables it.
- **`SudoAvatar.test.tsx`**: renders (a stable testid / label present).
- **`SudoOnboarding.test.tsx`** (mock `useMe`): renders the first step for a level-1 unseen account; hidden for a level-5 account; hidden once seen; **Next** advances Step 1 → Step 2 → Step 3 → dismiss (persisted); **Skip tour** dismisses + persists; missing `[data-tour]` target does not crash (renders centered card).

## Non-goals / deferred

- Backend completion flag / funnel analytics (chose localStorage + level-1 heuristic). Possible follow-up.
- Multiple SUDO mood faces in-app (one face for v1).
- Interactive "do it now" gating (the tour points, it doesn't force actions).
- Animation beyond simple CSS transitions.
- No new runtime dependencies; no Python changes.
