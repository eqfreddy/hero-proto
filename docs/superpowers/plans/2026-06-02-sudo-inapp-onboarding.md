# SUDO In-App Onboarding Tour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-session, skippable, SUDO-guided spotlight tour of the 3-step core loop (Summon → Team → Battle) for brand-new players, built on the existing CoachMark spotlight technique, with SUDO rendered as a styled CSS/SVG avatar.

**Architecture:** Frontend only. A pure gate hook (`useOnboarding`), a presentational `SudoAvatar`, step data (`onboardingSteps`), and a self-contained `SudoOnboarding` controller mounted in `Shell`. The controller reads `useMe()` for `account_level`, gates on a localStorage flag + the level-1 heuristic, spotlights nav hubs via `[data-tour]` attributes, and persists "seen" on skip/finish. No backend, no new deps.

**Tech Stack:** React 18 + TypeScript + Vite, vitest + @testing-library/react (run with `bun run test` from `frontend/` — NOT `bun test`). Inline styles + small CSS files, matching the existing `CoachMark`/`SummonRevealOverlay` patterns.

**Spec:** `docs/superpowers/specs/2026-06-02-sudo-inapp-onboarding-design.md`.

**Conventions:**
- Run tests: `cd frontend && bun run test [path]`. Build/typecheck: `bun run build`.
- Pre-existing pattern to mirror: `frontend/src/components/CoachMark.tsx` (localStorage seen-set, spotlight ring via `getBoundingClientRect`).
- `useMe()` (`frontend/src/hooks/useMe.ts`) returns `{ data: Me | undefined }`; `Me.account_level: number` (`frontend/src/types/index.ts`).
- `Shell.tsx` (`frontend/src/components/Layout/Shell.tsx`) renders `<PlayNav />`, `<ToastContainer />` etc. inside `<AgeGate>`.

---

## File structure

- **Create** `frontend/src/onboarding/useOnboarding.ts` — gate + persistence (pure logic).
- **Create** `frontend/src/onboarding/onboardingSteps.ts` — the 3 step definitions (data).
- **Create** `frontend/src/components/SudoAvatar.tsx` (+ `SudoAvatar.css`) — the CSS/SVG daemon face.
- **Create** `frontend/src/components/SudoOnboarding.tsx` (+ `SudoOnboarding.css`) — the tour controller.
- **Modify** `frontend/src/components/Layout/PlayNav.tsx` — add `data-tour` attrs to Heroes + Battle items.
- **Modify** `frontend/src/components/Layout/Shell.tsx` — mount `<SudoOnboarding />`.
- **Modify** `frontend/src/routes/Account.tsx` — add a "Replay intro" button.
- **Tests** colocated: `useOnboarding.test.ts`, `SudoAvatar.test.tsx`, `SudoOnboarding.test.tsx`.

---

### Task 1: `useOnboarding` — gate + persistence

**Files:**
- Create: `frontend/src/onboarding/useOnboarding.ts`
- Test: `frontend/src/onboarding/useOnboarding.test.ts`

- [ ] **Step 1: Write the failing test.** Create `frontend/src/onboarding/useOnboarding.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useShouldOnboard, markOnboardingSeen, replayOnboarding } from './useOnboarding'

describe('useOnboarding gate', () => {
  beforeEach(() => localStorage.clear())

  it('shows for a fresh level-1 account', () => {
    expect(useShouldOnboard(1)).toBe(true)
  })

  it('hides once marked seen', () => {
    markOnboardingSeen()
    expect(useShouldOnboard(1)).toBe(false)
  })

  it('hides for higher-level accounts even if unseen', () => {
    expect(useShouldOnboard(5)).toBe(false)
  })

  it('hides when account level is undefined (me not loaded)', () => {
    expect(useShouldOnboard(undefined)).toBe(false)
  })

  it('replayOnboarding re-enables it', () => {
    markOnboardingSeen()
    expect(useShouldOnboard(1)).toBe(false)
    replayOnboarding()
    expect(useShouldOnboard(1)).toBe(true)
  })
})
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun run test src/onboarding/useOnboarding.test.ts`
Expected: FAIL — module/exports not found.

- [ ] **Step 3: Implement.** Create `frontend/src/onboarding/useOnboarding.ts`:

```typescript
const KEY = 'heroproto_onboarding_seen'

export function hasSeenOnboarding(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function markOnboardingSeen(): void {
  try {
    localStorage.setItem(KEY, '1')
  } catch {
    /* best-effort: private mode / disabled storage */
  }
}

export function replayOnboarding(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* no-op */
  }
}

// Not reactive (localStorage isn't); recomputed each render. Named use* for
// call-site readability. Show only for a genuinely-new, not-yet-onboarded account.
export function useShouldOnboard(accountLevel: number | undefined): boolean {
  return accountLevel === 1 && !hasSeenOnboarding()
}
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun run test src/onboarding/useOnboarding.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/onboarding/useOnboarding.ts frontend/src/onboarding/useOnboarding.test.ts
git commit -m "feat(onboarding): localStorage gate + level-1 heuristic hook"
```

---

### Task 2: `SudoAvatar` — the CSS/SVG daemon face

**Files:**
- Create: `frontend/src/components/SudoAvatar.tsx`, `frontend/src/components/SudoAvatar.css`
- Test: `frontend/src/components/SudoAvatar.test.tsx`

- [ ] **Step 1: Write the failing test.** Create `frontend/src/components/SudoAvatar.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SudoAvatar } from './SudoAvatar'

describe('SudoAvatar', () => {
  it('renders the SUDO daemon face', () => {
    render(<SudoAvatar />)
    const el = screen.getByTestId('sudo-avatar')
    expect(el).toBeInTheDocument()
    expect(el.getAttribute('aria-label')).toBe('SUDO')
  })

  it('honors the size prop', () => {
    render(<SudoAvatar size={80} />)
    expect(screen.getByTestId('sudo-avatar').getAttribute('width')).toBe('80')
  })
})
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun run test src/components/SudoAvatar.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement.** Create `frontend/src/components/SudoAvatar.tsx`:

```tsx
import './SudoAvatar.css'

interface Props {
  size?: number
}

// SUDO as a little helpdesk daemon: a terminal-head creature with glowing
// eyes, a deadpan flat mouth, and a status antenna. Pure presentational SVG.
export function SudoAvatar({ size = 56 }: Props) {
  return (
    <svg
      className="sudo-avatar"
      data-testid="sudo-avatar"
      role="img"
      aria-label="SUDO"
      width={size}
      height={size}
      viewBox="0 0 64 64"
    >
      <defs>
        <linearGradient id="sudoFace" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1b2b3a" />
          <stop offset="1" stopColor="#0d1620" />
        </linearGradient>
      </defs>
      <line x1="32" y1="12" x2="32" y2="5" stroke="#00e0d0" strokeWidth="2" />
      <circle cx="32" cy="4" r="2.5" fill="#e8a35a" />
      <rect x="8" y="12" width="48" height="40" rx="11" fill="url(#sudoFace)" stroke="#00e0d0" strokeWidth="2" />
      <circle className="sudo-avatar-eye" cx="24" cy="30" r="4" fill="#00e0d0" />
      <circle className="sudo-avatar-eye" cx="40" cy="30" r="4" fill="#00e0d0" />
      <rect x="24" y="40" width="16" height="2.5" rx="1.25" fill="#5ad8ff" />
    </svg>
  )
}
```

Create `frontend/src/components/SudoAvatar.css`:

```css
.sudo-avatar {
  display: block;
  filter: drop-shadow(0 0 6px rgba(0, 224, 208, 0.35));
}
.sudo-avatar-eye {
  animation: sudo-blink 5.5s infinite;
}
@keyframes sudo-blink {
  0%, 92%, 100% { opacity: 1; }
  95% { opacity: 0.15; }
}
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun run test src/components/SudoAvatar.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/components/SudoAvatar.tsx frontend/src/components/SudoAvatar.css frontend/src/components/SudoAvatar.test.tsx
git commit -m "feat(onboarding): SudoAvatar CSS/SVG daemon face"
```

---

### Task 3: `SudoOnboarding` — the tour controller (+ step data)

**Files:**
- Create: `frontend/src/onboarding/onboardingSteps.ts`
- Create: `frontend/src/components/SudoOnboarding.tsx`, `frontend/src/components/SudoOnboarding.css`
- Test: `frontend/src/components/SudoOnboarding.test.tsx`

- [ ] **Step 1: Create the step data.** Create `frontend/src/onboarding/onboardingSteps.ts`:

```typescript
export interface OnboardingStep {
  tourTarget: string | null  // matches a [data-tour="..."] attr; null = no spotlight
  title: string
  body: string
}

// Steps 1 & 2 share the Heroes hub by design — recruiting and team-building
// both live there. SUDO's register: deadpan, a touch warmer for newcomers.
export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    tourTarget: 'heroes',
    title: 'Step 1 — Recruit',
    body: 'Summon your first recruits. They live under Heroes. Try not to whiff.',
  },
  {
    tourTarget: 'heroes',
    title: 'Step 2 — Build',
    body: 'Form a squad from what you pulled. Same place. Pick the ones that look expensive.',
  },
  {
    tourTarget: 'battle',
    title: 'Step 3 — Deploy',
    body: 'Throw them at a stage. This is the part that matters. Permission granted.',
  },
]
```

- [ ] **Step 2: Write the failing test.** Create `frontend/src/components/SudoOnboarding.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SudoOnboarding } from './SudoOnboarding'

const h = vi.hoisted(() => ({ level: 1 as number | undefined }))
vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: { account_level: h.level } }),
}))

describe('SudoOnboarding', () => {
  beforeEach(() => {
    localStorage.clear()
    h.level = 1
  })

  it('shows step 1 for a fresh level-1 account', () => {
    render(<SudoOnboarding />)
    expect(screen.getByText('Step 1 — Recruit')).toBeInTheDocument()
  })

  it('renders nothing for a higher-level account', () => {
    h.level = 5
    const { container } = render(<SudoOnboarding />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing once seen', () => {
    localStorage.setItem('heroproto_onboarding_seen', '1')
    const { container } = render(<SudoOnboarding />)
    expect(container).toBeEmptyDOMElement()
  })

  it('Next walks all three steps then dismisses + persists', () => {
    const { container } = render(<SudoOnboarding />)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2 — Build')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 3 — Deploy')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /got it/i }))
    expect(container).toBeEmptyDOMElement()
    expect(localStorage.getItem('heroproto_onboarding_seen')).toBe('1')
  })

  it('Skip dismisses immediately + persists', () => {
    const { container } = render(<SudoOnboarding />)
    fireEvent.click(screen.getByRole('button', { name: /skip tour/i }))
    expect(container).toBeEmptyDOMElement()
    expect(localStorage.getItem('heroproto_onboarding_seen')).toBe('1')
  })

  it('does not crash when the spotlight target is absent', () => {
    // No [data-tour] elements in the test DOM -> centered card, no ring.
    render(<SudoOnboarding />)
    expect(screen.getByText('Step 1 — Recruit')).toBeInTheDocument()
    expect(screen.queryByTestId('sudo-onb-ring')).toBeNull()
  })
})
```

- [ ] **Step 3: Run to verify it fails.** `cd frontend && bun run test src/components/SudoOnboarding.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement the controller.** Create `frontend/src/components/SudoOnboarding.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useMe } from '../hooks/useMe'
import { SudoAvatar } from './SudoAvatar'
import { ONBOARDING_STEPS } from '../onboarding/onboardingSteps'
import { useShouldOnboard, markOnboardingSeen } from '../onboarding/useOnboarding'
import './SudoOnboarding.css'

export function SudoOnboarding() {
  const { data: me } = useMe()
  const should = useShouldOnboard(me?.account_level)
  const [active, setActive] = useState(false)
  const [idx, setIdx] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)

  // Latch active once eligible so a dismiss stays dismissed this session.
  useEffect(() => {
    if (should) setActive(true)
  }, [should])

  const step = ONBOARDING_STEPS[idx]

  useEffect(() => {
    if (!active || !step) return
    function place() {
      const el = step.tourTarget
        ? document.querySelector(`[data-tour="${step.tourTarget}"]`)
        : null
      setRect(el ? el.getBoundingClientRect() : null)
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [active, step])

  if (!active || !step) return null

  function finish() {
    markOnboardingSeen()
    setActive(false)
  }
  function next() {
    if (idx >= ONBOARDING_STEPS.length - 1) finish()
    else setIdx((i) => i + 1)
  }
  const isLast = idx >= ONBOARDING_STEPS.length - 1

  return (
    <div className="sudo-onb" role="dialog" aria-modal="true" aria-label="Getting started">
      {rect && (
        <div
          data-testid="sudo-onb-ring"
          className="sudo-onb-ring"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
          }}
        />
      )}
      <div className="sudo-onb-card">
        <div className="sudo-onb-head">
          <SudoAvatar size={48} />
          <div className="sudo-onb-title">{step.title}</div>
        </div>
        <div className="sudo-onb-body">{step.body}</div>
        <div className="sudo-onb-dots" aria-hidden="true">
          {ONBOARDING_STEPS.map((_, i) => (
            <span key={i} className={'sudo-onb-dot' + (i === idx ? ' is-on' : '')} />
          ))}
        </div>
        <div className="sudo-onb-actions">
          <button className="sudo-onb-skip" onClick={finish}>Skip tour</button>
          <button className="sudo-onb-next" onClick={next}>{isLast ? 'Got it' : 'Next'}</button>
        </div>
      </div>
    </div>
  )
}
```

Create `frontend/src/components/SudoOnboarding.css`:

```css
.sudo-onb {
  position: fixed;
  inset: 0;
  z-index: 1400;
  background: rgba(3, 7, 14, 0.72);
}
.sudo-onb-ring {
  position: fixed;
  box-shadow: 0 0 0 3px var(--accent, #4ea1ff), 0 0 0 6px rgba(78, 161, 255, 0.22);
  border-radius: 8px;
  pointer-events: none;
  z-index: 1401;
  transition: all 0.25s ease;
}
.sudo-onb-card {
  position: fixed;
  left: 50%;
  bottom: 96px;
  transform: translateX(-50%);
  z-index: 1402;
  width: min(340px, calc(100vw - 32px));
  background: linear-gradient(180deg, var(--c-surface, #121821), var(--c-bg, #0b0d10));
  border: 1px solid rgba(0, 224, 208, 0.4);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.sudo-onb-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.sudo-onb-title {
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--c-text, #e7edf3);
}
.sudo-onb-body {
  font-size: 13px;
  line-height: 1.5;
  color: var(--c-muted, #9fb0c0);
  margin-bottom: 12px;
}
.sudo-onb-dots {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}
.sudo-onb-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
}
.sudo-onb-dot.is-on {
  background: #00e0d0;
}
.sudo-onb-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sudo-onb-skip {
  background: none;
  border: none;
  color: var(--c-muted, #9fb0c0);
  font-size: 12px;
  cursor: pointer;
}
.sudo-onb-next {
  background: #00e0d0;
  color: #04222020;
  color: #042; /* dark on cyan */
  border: none;
  border-radius: 8px;
  padding: 8px 18px;
  font-weight: 800;
  letter-spacing: 0.04em;
  cursor: pointer;
}
```

(Note: the `--c-*` / `--accent` CSS variables are the existing Chrome palette; the fallbacks keep it sane if a var is absent.)

- [ ] **Step 5: Run to verify it passes.** `cd frontend && bun run test src/components/SudoOnboarding.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/onboarding/onboardingSteps.ts frontend/src/components/SudoOnboarding.tsx frontend/src/components/SudoOnboarding.css frontend/src/components/SudoOnboarding.test.tsx
git commit -m "feat(onboarding): SUDO-guided 3-step spotlight tour controller"
```

---

### Task 4: Wire it in — PlayNav anchors, Shell mount, Account replay

**Files:**
- Modify: `frontend/src/components/Layout/PlayNav.tsx`
- Modify: `frontend/src/components/Layout/Shell.tsx`
- Modify: `frontend/src/routes/Account.tsx`

- [ ] **Step 1: Add `data-tour` anchors to PlayNav.** In `frontend/src/components/Layout/PlayNav.tsx`, the `slots.map((s) => ...)` renders a `<NavLink>` per slot. Add a `data-tour` attribute derived from the slot label so the tour can find the Heroes + Battle hubs. Find the `<NavLink ... key={s.path} to={s.path} className=...>` and add:

```tsx
            data-tour={s.label === 'Heroes' ? 'heroes' : s.label === 'Battle' ? 'battle' : undefined}
```

(Place it as an attribute on the `<NavLink>`. `undefined` renders no attribute for the other hubs.)

- [ ] **Step 2: Mount the tour in Shell.** In `frontend/src/components/Layout/Shell.tsx`, add the import near the other component imports:

```tsx
import { SudoOnboarding } from '../SudoOnboarding'
```

Then mount it inside the `chrome-root` tree, right after `<PlayNav />`:

```tsx
        <PlayNav />
        <SudoOnboarding />
```

- [ ] **Step 3: Add a "Replay intro" affordance to Account.** Read `frontend/src/routes/Account.tsx` to find a sensible spot (near other settings/links). Add the import:

```tsx
import { replayOnboarding } from '../onboarding/useOnboarding'
import { useNavigate } from 'react-router-dom'
```

(If `useNavigate` is already imported, don't duplicate it.) Add a low-key button in the settings list:

```tsx
        <button
          type="button"
          onClick={() => { replayOnboarding(); navigate('/app/me') }}
          style={{ background: 'none', border: '1px solid var(--c-line, #28303a)', borderRadius: 8, padding: '8px 14px', color: 'var(--c-muted, #9fb0c0)', fontSize: 12, cursor: 'pointer' }}
        >
          Replay intro tour
        </button>
```

Ensure a `const navigate = useNavigate()` exists in the component (add it if not already present). Note: the tour re-fires on `/app/me` only if the account is still level 1; for higher-level accounts the localStorage flag clears but the level-1 heuristic keeps it hidden (acceptable — the replay is primarily a fresh-account/dev affordance).

- [ ] **Step 4: Typecheck + build.** `cd frontend && bun run build`
Expected: clean (`tsc -b` passes; vite build succeeds). Fix any type errors (e.g., an unused import or a missing `navigate`).

- [ ] **Step 5: Full frontend suite.** `cd frontend && bun run test 2>&1 | tail -6`
Expected: all green (the prior 122 + the new onboarding tests). If a snapshot of Shell or PlayNav exists and trips on the new element/attribute, update it to include the addition (don't remove the feature).

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/components/Layout/PlayNav.tsx frontend/src/components/Layout/Shell.tsx frontend/src/routes/Account.tsx
git commit -m "feat(onboarding): mount SUDO tour in shell + nav anchors + replay link"
```

---

### Task 5: Build artifact + final verification

**Files:** none (build output + verification)

- [ ] **Step 1: Production build (regenerates committed SPA).** `cd frontend && bun run build`
Expected: clean; writes `app/static/spa/*`.

- [ ] **Step 2: Commit the rebuilt SPA.**

```bash
git add app/static/spa
git commit -m "build(spa): rebuild with SUDO in-app onboarding"
```

- [ ] **Step 3: Manual smoke (optional, recommended).** Start the server (`HEROPROTO_MOCK_PAYMENTS_ENABLED=1 uv run uvicorn app.main:app --port 8000`), register a fresh account in the SPA at `http://127.0.0.1:8000/app/`, and confirm: on first lobby load SUDO's card appears spotlighting the Heroes hub; Next walks to Battle; Skip/finish dismisses and it does not reappear on reload; an existing (level > 1) account never sees it.

---

## Self-review notes

- **Spec coverage:** gate hook + level-1 heuristic + localStorage + `replayOnboarding` (T1); SudoAvatar styled CSS/SVG face (T2); 3 steps Summon→Team→Battle + controller with spotlight/Next/Skip/persist/missing-target-safe (T3); PlayNav `data-tour` anchors + Shell mount + Account replay link (T4); build artifact (T5). All testing bullets from the spec map to T1/T2/T3 tests.
- **Placeholder scan:** none — every step has complete code.
- **Type/name consistency:** `useShouldOnboard(accountLevel)`, `markOnboardingSeen`, `replayOnboarding`, `hasSeenOnboarding`, `ONBOARDING_STEPS`/`OnboardingStep{tourTarget,title,body}`, `SudoAvatar({size})`, `SudoOnboarding` are used identically across tasks. localStorage key `heroproto_onboarding_seen` matches between hook, controller, and test. `[data-tour]` values `heroes`/`battle` match between PlayNav (T4) and onboardingSteps (T3).
- **No backend / no new deps.** CI-safe (jsdom tests, no network).
- **SDT/Rule #1:** Skip on every step; never blocks progress; only fires for new accounts; fully dismissible + replayable.
- **Known soft spot:** the Account "Replay intro" placement depends on `Account.tsx`'s structure (T4 Step 3 reads it first). The replay is most meaningful for level-1 accounts (the heuristic still gates higher levels) — documented as acceptable.
