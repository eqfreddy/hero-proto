# SPA Rewrite — Part 4: Battle Routes + HTMX Cutover

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add all four `/battle/*` routes (Setup, Replay/Watch, Interactive/Play, and a shared BattleHUD overlay), then cut over FastAPI from HTMX to the React SPA by deleting the HTMX layer and rewriting `ui.py`.

**Architecture:** Battle routes live outside the `/app` shell in a full-screen layout. A `useRef` + `useEffect` pattern mounts/destroys Phaser into a host `<div>` while React owns the HUD overlay. After all battle routes pass a smoke test, the HTMX layer (templates, partials JS, standalone HTML files) is deleted and `ui.py` is swapped to a minimal SPA catch-all.

**Tech Stack:** React 18 + TypeScript, React Router v6, TanStack Query v5, Phaser 3 (CDN via `<script>` in `index.html` during transition; importable from `window.Phaser`), Zustand auth store, `apiFetch` wrapper.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `frontend/src/routes/battle/BattleSetupRoute.tsx` | Create | Team picker + stage selector; POSTs `/battles` or `/battles/interactive/start` |
| `frontend/src/routes/battle/BattleReplayRoute.tsx` | Create | Phaser replay viewer (`/battle/:id/replay` and `/battle/:id/watch`) |
| `frontend/src/routes/battle/BattlePlayRoute.tsx` | Create | Interactive session UI — action strip + unit cards, POSTs `/battles/interactive/:session_id/act` |
| `frontend/src/routes/battle/BattleLayout.tsx` | Create | Full-screen wrapper (no nav header) shared by all `/battle/*` routes |
| `frontend/src/components/BattleHUD.tsx` | Create | DOM overlay: HP bars, speed controls, rewards modal — rendered by replay + play routes |
| `frontend/src/hooks/useBattleLog.ts` | Create | `useQuery` wrapper for `GET /battles/:id` |
| `frontend/src/hooks/useInteractiveSession.ts` | Create | State machine for interactive — holds session state, exposes `act()` |
| `frontend/src/types/battle.ts` | Create | `BattleOut`, `InteractiveStateOut`, `CombatUnit` TypeScript interfaces |
| `frontend/src/api/battles.ts` | Create | Typed fetch wrappers: `postBattle()`, `postInteractiveStart()`, `postAct()` |
| `frontend/index.html` | Modify | Add Phaser CDN `<script>` tag (removed at cutover when bundled) |
| `app/routers/ui.py` | Modify (cutover) | Delete all partial routes; replace shell route with SPA catch-all |
| `app/templates/partials/` | Delete (cutover) | All 15 partial templates |
| `app/templates/shell.html` | Delete (cutover) | HTMX shell |
| `app/templates/base.html` | Delete (cutover) | HTMX base |
| `app/static/battle-setup.html` | Delete (cutover) | Replaced by BattleSetupRoute |
| `app/static/battle-phaser.html` | Delete (cutover) | Replaced by BattleReplayRoute |
| `app/static/battle-interactive.html` | Delete (cutover) | Replaced by BattlePlayRoute |
| `app/static/battle-replay.html` | Delete (cutover) | Replaced by BattleReplayRoute |
| `app/static/battle-pixi.html` | Delete (cutover) | Plan B prototype; superseded |
| `app/static/team-picker.js` | Delete (cutover) | Logic now in BattleSetupRoute |
| `app/static/in-app-viewer.js` | Delete (cutover) | Logic now in BattleReplayRoute |
| `app/static/tutorial-hints.js` | Delete (cutover) | Logic now in React |
| `app/static/toast.js` | Delete (cutover) | Replaced by Zustand ui store |
| `app/static/sound.js` | Delete (cutover) | Replaced by Zustand sound store |

---

## Task 1: Battle TypeScript types + API wrappers

**Files:**
- Create: `frontend/src/types/battle.ts`
- Create: `frontend/src/api/battles.ts`
- Test: `frontend/src/api/battles.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/api/battles.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postBattle, postInteractiveStart, postAct } from './battles'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('postBattle', () => {
  it('posts correct payload to /battles', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: 42, account_id: 1, log: [] }),
    })
    const result = await postBattle({ stage_id: 3, team: [1, 2, 3], target_priority: 'lowest_hp' })
    expect(mockFetch).toHaveBeenCalledWith(
      '/battles',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ stage_id: 3, team: [1, 2, 3], target_priority: 'lowest_hp' }),
      }),
    )
    expect(result.id).toBe(42)
  })
})

describe('postInteractiveStart', () => {
  it('posts to /battles/interactive/start', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'abc', pending: null, team_a: [], team_b: [] }),
    })
    const result = await postInteractiveStart({ stage_id: 3, team: [1, 2] })
    expect(mockFetch).toHaveBeenCalledWith('/battles/interactive/start', expect.any(Object))
    expect(result.session_id).toBe('abc')
  })
})

describe('postAct', () => {
  it('posts target_uid to /battles/interactive/:sessionId/act', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'abc', pending: null, team_a: [], team_b: [] }),
    })
    await postAct('abc', 'unit-uid-1')
    expect(mockFetch).toHaveBeenCalledWith(
      '/battles/interactive/abc/act',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ target_uid: 'unit-uid-1' }) }),
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/api/battles.test.ts
```

Expected: FAIL — `battles.ts` not found.

- [ ] **Step 3: Write the types**

```typescript
// frontend/src/types/battle.ts
export interface CombatUnit {
  uid: string
  name: string
  hp: number
  max_hp: number
  atk: number
  def: number
  spd: number
  dead: boolean
  portrait_url?: string
}

export interface BattleLog {
  event: string
  [key: string]: unknown
}

export interface BattleOut {
  id: number
  account_id: number
  stage_id?: number
  log: BattleLog[]
  created_at?: string
}

export interface InteractivePending {
  actor_uid: string
  valid_targets: string[]
}

export interface InteractiveStateOut {
  session_id: string
  team_a: CombatUnit[]
  team_b: CombatUnit[]
  pending: InteractivePending | null
  rewards?: Record<string, number>
  done?: boolean
}

export interface PostBattlePayload {
  stage_id: number
  team: number[]
  target_priority?: string
}

export interface PostInteractiveStartPayload {
  stage_id: number
  team: number[]
}
```

- [ ] **Step 4: Write the API wrappers**

```typescript
// frontend/src/api/battles.ts
import { apiFetch } from './client'
import type { BattleOut, InteractiveStateOut, PostBattlePayload, PostInteractiveStartPayload } from '../types/battle'

export function postBattle(payload: PostBattlePayload): Promise<BattleOut> {
  return apiFetch<BattleOut>('/battles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function postInteractiveStart(payload: PostInteractiveStartPayload): Promise<InteractiveStateOut> {
  return apiFetch<InteractiveStateOut>('/battles/interactive/start', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function postAct(sessionId: string, targetUid: string): Promise<InteractiveStateOut> {
  return apiFetch<InteractiveStateOut>(`/battles/interactive/${sessionId}/act`, {
    method: 'POST',
    body: JSON.stringify({ target_uid: targetUid }),
  })
}

export function fetchBattle(battleId: string | number): Promise<BattleOut> {
  return apiFetch<BattleOut>(`/battles/${battleId}`)
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/api/battles.test.ts
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/battle.ts frontend/src/api/battles.ts frontend/src/api/battles.test.ts
git commit -m "feat(spa): battle types + API wrappers (postBattle, postInteractiveStart, postAct)"
```

---

## Task 2: Battle data hooks

**Files:**
- Create: `frontend/src/hooks/useBattleLog.ts`
- Create: `frontend/src/hooks/useInteractiveSession.ts`
- Test: `frontend/src/hooks/useBattleLog.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/hooks/useBattleLog.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { useBattleLog } from './useBattleLog'

vi.mock('../api/battles', () => ({
  fetchBattle: vi.fn(async (id) => ({ id: Number(id), account_id: 1, log: [{ event: 'start' }] })),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useBattleLog', () => {
  it('fetches battle by id', async () => {
    const { result } = renderHook(() => useBattleLog('42'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.id).toBe(42)
    expect(result.current.data?.log).toHaveLength(1)
  })

  it('skips fetch when id is undefined', () => {
    const { result } = renderHook(() => useBattleLog(undefined), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/hooks/useBattleLog.test.tsx
```

Expected: FAIL — `useBattleLog.ts` not found.

- [ ] **Step 3: Write `useBattleLog`**

```typescript
// frontend/src/hooks/useBattleLog.ts
import { useQuery } from '@tanstack/react-query'
import { fetchBattle } from '../api/battles'
import type { BattleOut } from '../types/battle'

export function useBattleLog(battleId: string | number | undefined) {
  return useQuery<BattleOut>({
    queryKey: ['battle', battleId],
    queryFn: () => fetchBattle(battleId!),
    enabled: battleId != null,
    staleTime: Infinity,
  })
}
```

- [ ] **Step 4: Write `useInteractiveSession`**

This hook is a state machine — no test file needed because it wraps `postAct` directly and is covered by the interactive route's integration.

```typescript
// frontend/src/hooks/useInteractiveSession.ts
import { useState, useCallback } from 'react'
import { postAct } from '../api/battles'
import type { InteractiveStateOut } from '../types/battle'

export function useInteractiveSession(initialState: InteractiveStateOut | null) {
  const [state, setState] = useState<InteractiveStateOut | null>(initialState)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const act = useCallback(async (targetUid: string) => {
    if (!state) return
    setActing(true)
    setError(null)
    try {
      const next = await postAct(state.session_id, targetUid)
      setState(next)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setActing(false)
    }
  }, [state])

  return { state, setState, act, acting, error }
}
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx vitest run src/hooks/useBattleLog.test.tsx
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useBattleLog.ts frontend/src/hooks/useInteractiveSession.ts frontend/src/hooks/useBattleLog.test.tsx
git commit -m "feat(spa): useBattleLog query hook + useInteractiveSession state machine"
```

---

## Task 3: Battle layout + BattleHUD component

**Files:**
- Create: `frontend/src/routes/battle/BattleLayout.tsx`
- Create: `frontend/src/components/BattleHUD.tsx`
- Test: `frontend/src/components/BattleHUD.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/BattleHUD.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BattleHUD } from './BattleHUD'
import type { CombatUnit } from '../types/battle'

const makeUnit = (uid: string, hp: number, max_hp: number, dead = false): CombatUnit => ({
  uid, name: uid, hp, max_hp, atk: 100, def: 50, spd: 10, dead,
})

describe('BattleHUD', () => {
  it('renders unit name and hp bar', () => {
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[makeUnit('enemy-1', 60, 120)]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />
    )
    expect(screen.getByText('hero-1')).toBeTruthy()
    expect(screen.getByText('enemy-1')).toBeTruthy()
  })

  it('marks dead units', () => {
    render(
      <BattleHUD
        teamA={[makeUnit('dead-hero', 0, 100, true)]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />
    )
    expect(screen.getByText('dead-hero').closest('[data-dead]')).toBeTruthy()
  })

  it('shows rewards overlay when done=true', () => {
    render(
      <BattleHUD
        teamA={[]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={true}
        rewards={{ coins: 150, gems: 0, shards: 1 }}
        onClose={() => {}}
      />
    )
    expect(screen.getByText(/150/)).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/BattleHUD.test.tsx
```

Expected: FAIL — `BattleHUD.tsx` not found.

- [ ] **Step 3: Write `BattleLayout`**

```tsx
// frontend/src/routes/battle/BattleLayout.tsx
import { Outlet } from 'react-router-dom'

export default function BattleLayout() {
  return (
    <div style={{ width: '100vw', height: '100vh', background: 'var(--color-bg)', overflow: 'hidden', position: 'relative' }}>
      <Outlet />
    </div>
  )
}
```

- [ ] **Step 4: Write `BattleHUD`**

```tsx
// frontend/src/components/BattleHUD.tsx
import type { CombatUnit } from '../types/battle'

interface BattleHUDProps {
  teamA: CombatUnit[]
  teamB: CombatUnit[]
  onAct: ((targetUid: string) => void) | undefined
  pendingActorUid: string | null
  validTargets: string[]
  acting: boolean
  done: boolean
  rewards: Record<string, number> | null
  onClose: () => void
}

function UnitCard({ unit, isTarget, onSelect }: { unit: CombatUnit; isTarget: boolean; onSelect?: () => void }) {
  const pct = unit.max_hp > 0 ? Math.max(0, unit.hp / unit.max_hp) : 0
  return (
    <div
      data-dead={unit.dead || undefined}
      onClick={isTarget && onSelect ? onSelect : undefined}
      style={{
        padding: '6px 8px',
        border: isTarget ? '2px solid var(--color-accent)' : '1px solid rgba(255,255,255,0.1)',
        borderRadius: 6,
        opacity: unit.dead ? 0.4 : 1,
        cursor: isTarget ? 'pointer' : 'default',
        minWidth: 90,
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text)', marginBottom: 3 }}>{unit.name}</div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct * 100}%`, height: '100%', background: unit.dead ? '#666' : 'var(--color-accent)', transition: 'width 0.3s' }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--color-muted)', marginTop: 2 }}>{unit.hp} / {unit.max_hp}</div>
    </div>
  )
}

export function BattleHUD({ teamA, teamB, onAct, pendingActorUid, validTargets, acting, done, rewards, onClose }: BattleHUDProps) {
  const validSet = new Set(validTargets)

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: 16 }}>
      {/* Team B (enemies) — top */}
      <div style={{ display: 'flex', gap: 8, pointerEvents: 'auto' }}>
        {teamB.map(u => (
          <UnitCard
            key={u.uid}
            unit={u}
            isTarget={!!onAct && validSet.has(u.uid)}
            onSelect={onAct ? () => onAct(u.uid) : undefined}
          />
        ))}
      </div>

      {/* Team A (player) — bottom */}
      <div style={{ display: 'flex', gap: 8, pointerEvents: 'auto' }}>
        {teamA.map(u => (
          <UnitCard
            key={u.uid}
            unit={u}
            isTarget={false}
          />
        ))}
      </div>

      {/* Rewards overlay */}
      {done && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.75)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          pointerEvents: 'auto',
        }}>
          <div style={{ background: 'var(--color-surface)', borderRadius: 12, padding: 32, textAlign: 'center', minWidth: 260 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--color-text)', marginBottom: 16 }}>Battle Complete</div>
            {rewards && Object.entries(rewards).filter(([, v]) => v > 0).map(([k, v]) => (
              <div key={k} style={{ fontSize: 14, color: 'var(--color-muted)', marginBottom: 4 }}>+{v} {k}</div>
            ))}
            <button
              onClick={onClose}
              style={{ marginTop: 20, padding: '10px 28px', background: 'var(--color-accent)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 700 }}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {acting && (
        <div style={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.7)', color: '#fff', padding: '4px 12px', borderRadius: 4, fontSize: 12, pointerEvents: 'none' }}>
          Acting…
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx vitest run src/components/BattleHUD.test.tsx
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/battle/BattleLayout.tsx frontend/src/components/BattleHUD.tsx frontend/src/components/BattleHUD.test.tsx
git commit -m "feat(spa): BattleLayout full-screen shell + BattleHUD DOM overlay"
```

---

## Task 4: Battle Setup route

**Files:**
- Create: `frontend/src/routes/battle/BattleSetupRoute.tsx`

No unit test — this route relies on live API calls (covered by Playwright smoke test in Task 7).

- [ ] **Step 1: Add Phaser CDN script to index.html**

Phaser is used by the replay route. Load it globally so the CDN is cached during development; it will be replaced with a bundled import at cutover.

```html
<!-- frontend/index.html — add inside <head>, after the existing tags -->
<script src="https://cdn.jsdelivr.net/npm/phaser@3/dist/phaser.min.js"></script>
```

- [ ] **Step 2: Write `BattleSetupRoute`**

```tsx
// frontend/src/routes/battle/BattleSetupRoute.tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { postBattle, postInteractiveStart } from '../../api/battles'
import { useToastStore } from '../../store/ui'
import type { Hero } from '../../types'
import type { Stage } from '../../types'

function useHeroes() {
  return useQuery<Hero[]>({ queryKey: ['heroes'], queryFn: () => apiFetch('/heroes/mine'), staleTime: 5 * 60_000 })
}

function useStages() {
  return useQuery<Stage[]>({ queryKey: ['stages'], queryFn: () => apiFetch('/stages'), staleTime: 10 * 60_000 })
}

export default function BattleSetupRoute() {
  const navigate = useNavigate()
  const addToast = useToastStore(s => s.addToast)
  const { data: heroes = [] } = useHeroes()
  const { data: stages = [] } = useStages()

  const [team, setTeam] = useState<(number | null)[]>([null, null, null])
  const [selectedStageId, setSelectedStageId] = useState<number | null>(null)
  const [interactive, setInteractive] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const teamIds = team.filter((id): id is number => id !== null)
  const teamPower = teamIds
    .map(id => heroes.find(h => h.id === id))
    .filter(Boolean)
    .reduce((sum, h) => sum + (h!.power ?? 0), 0)

  function toggleHero(heroId: number) {
    setTeam(prev => {
      const idx = prev.indexOf(heroId)
      if (idx !== -1) {
        const next = [...prev]
        next[idx] = null
        return next
      }
      const empty = prev.findIndex(s => s === null)
      if (empty === -1) return prev
      const next = [...prev]
      next[empty] = heroId
      return next
    })
  }

  async function handleFight() {
    if (teamIds.length === 0 || !selectedStageId) return
    setSubmitting(true)
    try {
      if (interactive) {
        const state = await postInteractiveStart({ stage_id: selectedStageId, team: teamIds })
        navigate(`/battle/${state.session_id}/play`, { state: { initState: state } })
      } else {
        const battle = await postBattle({ stage_id: selectedStageId, team: teamIds, target_priority: 'lowest_hp' })
        navigate(`/battle/${battle.id}/replay`)
      }
    } catch (e) {
      addToast({ message: e instanceof Error ? e.message : 'Battle failed', kind: 'error' })
    } finally {
      setSubmitting(false)
    }
  }

  const selectedStage = stages.find(s => s.id === selectedStageId)

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto', color: 'var(--color-text)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button onClick={() => navigate('/app/stages')} style={{ background: 'none', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 14 }}>
          ← Back
        </button>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Battle Setup</h1>
      </div>

      {/* Stage selector */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Select Stage</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {stages.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedStageId(s.id)}
              style={{
                padding: '8px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                background: selectedStageId === s.id ? 'var(--color-accent)' : 'var(--color-surface)',
                color: selectedStageId === s.id ? '#fff' : 'var(--color-text)',
                border: '1px solid ' + (selectedStageId === s.id ? 'var(--color-accent)' : 'rgba(255,255,255,0.1)'),
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
        {selectedStage && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-muted)' }}>
            Energy cost: {selectedStage.energy_cost} · Recommended power: {selectedStage.recommended_power ?? '—'}
          </div>
        )}
      </section>

      {/* Team builder */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
          Your Team <span style={{ fontWeight: 400, color: 'var(--color-muted)' }}>— Power {teamPower}</span>
        </h2>
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          {team.map((heroId, idx) => {
            const hero = heroes.find(h => h.id === heroId)
            return (
              <div
                key={idx}
                onClick={() => heroId !== null && setTeam(prev => { const n = [...prev]; n[idx] = null; return n })}
                style={{
                  width: 80, height: 90, borderRadius: 8, border: '2px dashed rgba(255,255,255,0.15)',
                  background: hero ? 'var(--color-surface)' : 'transparent',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: hero ? 'pointer' : 'default', fontSize: 11, color: 'var(--color-muted)',
                }}
              >
                {hero ? (
                  <>
                    <div style={{ fontWeight: 700, color: 'var(--color-text)', textAlign: 'center', padding: '0 4px' }}>{hero.name}</div>
                    <div style={{ color: 'var(--color-muted)', marginTop: 2 }}>Lv {hero.level}</div>
                    <div style={{ fontSize: 10, marginTop: 2, color: 'rgba(255,255,255,0.3)' }}>click to remove</div>
                  </>
                ) : (
                  <span>Slot {idx + 1}</span>
                )}
              </div>
            )
          })}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {[...heroes].sort((a, b) => (b.power ?? 0) - (a.power ?? 0)).map(h => {
            const selected = team.includes(h.id)
            return (
              <button
                key={h.id}
                onClick={() => toggleHero(h.id)}
                style={{
                  padding: '6px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  background: selected ? 'var(--color-accent)' : 'var(--color-surface)',
                  color: selected ? '#fff' : 'var(--color-text)',
                  border: '1px solid ' + (selected ? 'var(--color-accent)' : 'rgba(255,255,255,0.1)'),
                }}
              >
                {h.name} ({h.power})
              </button>
            )
          })}
        </div>
      </section>

      {/* Interactive toggle + Fight button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--color-muted)' }}>
          <input
            type="checkbox"
            checked={interactive}
            onChange={e => setInteractive(e.target.checked)}
            style={{ width: 16, height: 16, accentColor: 'var(--color-accent)', cursor: 'pointer' }}
          />
          Interactive mode
        </label>
        <button
          onClick={handleFight}
          disabled={teamIds.length === 0 || !selectedStageId || submitting}
          style={{
            padding: '12px 32px', borderRadius: 8, fontSize: 15, fontWeight: 800, cursor: 'pointer',
            background: 'var(--color-accent)', color: '#fff', border: 'none',
            opacity: (teamIds.length === 0 || !selectedStageId || submitting) ? 0.5 : 1,
          }}
        >
          {submitting ? 'Starting…' : 'Fight!'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Wire route into App.tsx**

Open `frontend/src/App.tsx`. The `/battle` route tree should already have a `setup` child from Plan 1's scaffold (using `<Stub />`). Replace the stub:

```tsx
// In App.tsx — change the battle/setup child from:
{ path: 'setup', element: <Stub label="Battle Setup" /> }

// to:
{ path: 'setup', element: <BattleSetupRoute /> }
```

Add the import at the top of App.tsx:
```tsx
import BattleSetupRoute from './routes/battle/BattleSetupRoute'
```

- [ ] **Step 4: Manual smoke test**

Run the dev server:
```bash
cd frontend && npm run dev
```
Navigate to `http://localhost:5173/battle/setup`. Verify:
- Heroes list populates from `/heroes/mine`
- Stages list populates from `/stages`
- Selecting heroes fills team slots; clicking again removes them
- Fight button is disabled until hero + stage selected
- Clicking Fight (non-interactive) POSTs `/battles` and navigates to `/battle/:id/replay`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/battle/BattleSetupRoute.tsx frontend/index.html frontend/src/App.tsx
git commit -m "feat(spa): BattleSetupRoute — team picker + stage selector, auto + interactive launch"
```

---

## Task 5: Battle Replay + Interactive Play routes

**Files:**
- Create: `frontend/src/routes/battle/BattleReplayRoute.tsx`
- Create: `frontend/src/routes/battle/BattlePlayRoute.tsx`

- [ ] **Step 1: Write `BattleReplayRoute`**

This mounts Phaser 3 into a `canvasRef` div via `useEffect`. Phaser is available as `window.Phaser` from the CDN script added in Task 4.

```tsx
// frontend/src/routes/battle/BattleReplayRoute.tsx
import { useRef, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useBattleLog } from '../../hooks/useBattleLog'
import { BattleHUD } from '../../components/BattleHUD'

declare const Phaser: typeof import('phaser')

const CANVAS_W = 960
const CANVAS_H = 540

export default function BattleReplayRoute() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const canvasRef = useRef<HTMLDivElement>(null)
  const { data: battle, isLoading, error } = useBattleLog(id)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!canvasRef.current || !battle) return

    class ReplayScene extends Phaser.Scene {
      private cursor = 0
      private timer: Phaser.Time.TimerEvent | null = null
      private unitSprites: Map<string, Phaser.GameObjects.Rectangle> = new Map()
      private unitTexts: Map<string, Phaser.GameObjects.Text> = new Map()

      create() {
        this.cameras.main.setBackgroundColor('#0b0d10')

        // Initialise units from first two events or log metadata
        const units = this.extractUnits()
        units.forEach((u, i) => {
          const x = u.side === 'a' ? 200 + i * 120 : CANVAS_W - 200 - i * 120
          const y = CANVAS_H / 2
          const rect = this.add.rectangle(x, y, 60, 80, u.side === 'a' ? 0x59a0ff : 0xff7a59)
          this.unitSprites.set(u.uid, rect)
          const label = this.add.text(x, y + 50, u.name ?? u.uid, {
            fontSize: '11px', color: '#ffffff', align: 'center',
          }).setOrigin(0.5)
          this.unitTexts.set(u.uid, label)
        })

        this.timer = this.time.addEvent({ delay: 600, callback: this.tick, callbackScope: this, loop: true })
      }

      private extractUnits(): { uid: string; name?: string; side: string }[] {
        const seen = new Map<string, { uid: string; name?: string; side: string }>()
        for (const ev of battle!.log) {
          for (const side of ['a', 'b']) {
            const uid = (ev as Record<string, unknown>)[`${side}_uid`] as string | undefined
            if (uid && !seen.has(uid)) seen.set(uid, { uid, name: (ev as Record<string, unknown>)[`${side}_name`] as string | undefined, side })
          }
        }
        return Array.from(seen.values())
      }

      private tick() {
        if (this.cursor >= battle!.log.length) {
          this.timer?.remove()
          setDone(true)
          return
        }
        const ev = battle!.log[this.cursor] as Record<string, unknown>
        if (ev.event === 'damage') {
          const targetSprite = this.unitSprites.get(ev.target_uid as string)
          if (targetSprite) {
            this.tweens.add({ targets: targetSprite, alpha: 0.3, duration: 80, yoyo: true })
          }
        }
        this.cursor++
      }
    }

    const game = new Phaser.Game({
      type: Phaser.AUTO,
      width: CANVAS_W,
      height: CANVAS_H,
      parent: canvasRef.current,
      scene: ReplayScene,
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    })

    return () => { game.destroy(true) }
  }, [battle])

  if (isLoading) return <div style={{ color: 'var(--color-muted)', padding: 24 }}>Loading battle…</div>
  if (error) return <div style={{ color: 'var(--color-error)', padding: 24 }}>Failed to load battle.</div>

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh' }}>
      <div ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      <BattleHUD
        teamA={[]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={done}
        rewards={null}
        onClose={() => navigate('/app/stages')}
      />
    </div>
  )
}
```

- [ ] **Step 2: Write `BattlePlayRoute`**

```tsx
// frontend/src/routes/battle/BattlePlayRoute.tsx
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useInteractiveSession } from '../../hooks/useInteractiveSession'
import { BattleHUD } from '../../components/BattleHUD'
import type { InteractiveStateOut } from '../../types/battle'

export default function BattlePlayRoute() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const initState = (location.state as { initState?: InteractiveStateOut } | null)?.initState ?? null

  const { state, act, acting, error } = useInteractiveSession(initState)

  if (!state) {
    return (
      <div style={{ color: 'var(--color-muted)', padding: 24 }}>
        No session found. <button onClick={() => navigate('/battle/setup')} style={{ color: 'var(--color-accent)', background: 'none', border: 'none', cursor: 'pointer' }}>Start a new battle</button>
      </div>
    )
  }

  const done = state.done ?? false
  const pending = state.pending
  const rewards = state.rewards ?? null

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh', background: 'var(--color-bg)' }}>
      {/* Placeholder canvas background — swap for Phaser/Pixi when Plan B rigs land */}
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'rgba(255,255,255,0.08)', fontSize: 48, fontWeight: 900, letterSpacing: 4 }}>BATTLE</div>
      </div>

      <BattleHUD
        teamA={state.team_a}
        teamB={state.team_b}
        onAct={pending ? act : undefined}
        pendingActorUid={pending?.actor_uid ?? null}
        validTargets={pending?.valid_targets ?? []}
        acting={acting}
        done={done}
        rewards={rewards}
        onClose={() => navigate('/app/stages')}
      />

      {error && (
        <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', background: 'var(--color-error)', color: '#fff', padding: '8px 16px', borderRadius: 6, fontSize: 13 }}>
          {error}
        </div>
      )}

      {pending && !done && (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.7)', color: '#fff', padding: '8px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600 }}>
          {state.team_a.find(u => u.uid === pending.actor_uid)?.name ?? pending.actor_uid} — pick a target
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire routes into App.tsx**

```tsx
// Replace stubs in the /battle children array:
{ path: ':id/replay', element: <BattleReplayRoute /> },
{ path: ':id/watch',  element: <BattleReplayRoute /> },
{ path: ':id/play',   element: <BattlePlayRoute /> },
```

Add imports:
```tsx
import BattleReplayRoute from './routes/battle/BattleReplayRoute'
import BattlePlayRoute from './routes/battle/BattlePlayRoute'
```

- [ ] **Step 4: Manual smoke test**

1. Navigate to `/battle/setup`, pick heroes + stage, click Fight (non-interactive) → you should land on `/battle/:id/replay` and see the Phaser canvas animating.
2. Go back to setup, enable Interactive mode, click Fight → land on `/battle/:id/play`, see unit cards in BattleHUD, click an enemy target → state advances, button greys while acting.
3. Let the battle finish → Rewards overlay appears, click Continue → back to `/app/stages`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/battle/BattleReplayRoute.tsx frontend/src/routes/battle/BattlePlayRoute.tsx frontend/src/App.tsx
git commit -m "feat(spa): BattleReplayRoute (Phaser canvas) + BattlePlayRoute (interactive session)"
```

---

## Task 6: HTMX cutover — delete old layer + rewrite ui.py

**Prerequisite:** All tab routes (Plans 1–3) and all battle routes (Tasks 1–5 above) are implemented and manually verified against the live API.

**Files:**
- Modify: `app/routers/ui.py`
- Delete: all HTMX templates and standalone JS/HTML files

- [ ] **Step 1: Build the SPA**

```bash
cd frontend && npm run build
```

Expected: `app/static/spa/` populated with `index.html`, `assets/` JS and CSS chunks.

Verify the build output serves correctly:
```bash
cd .. && uvicorn app.main:app --port 8000 &
curl -I http://localhost:8000/app/static/spa/index.html
```

Expected: `200 OK` with `Content-Type: text/html`.

- [ ] **Step 2: Rewrite `app/routers/ui.py`**

The new `ui.py` keeps only: the SPA catch-all, the placeholder hero SVG endpoint, and the admin panel. All partial routes and HTMX imports are deleted.

Replace the entire contents of `app/routers/ui.py`:

```python
"""UI router — serves the React SPA and the placeholder hero SVG."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import HeroTemplate

router = APIRouter(prefix="/app", tags=["ui"], include_in_schema=False)

_SPA_DIR = Path(__file__).resolve().parents[1] / "static" / "spa"
_INDEX = _SPA_DIR / "index.html"


@router.get("/{full_path:path}", response_class=FileResponse)
def spa_shell(full_path: str) -> FileResponse:
    """Catch-all: serve the SPA index for all /app/* routes. React Router
    handles client-side routing from there."""
    return FileResponse(str(_INDEX))


# --- Placeholder portraits ---------------------------------------------------

_ROLE_COLORS = {"ATK": "#ff7a59", "DEF": "#59a0ff", "SUP": "#6dd39a"}
_RARITY_FRAMES = {
    "COMMON": "#9ca7b3", "UNCOMMON": "#6dd39a",
    "RARE": "#59a0ff", "EPIC": "#c97aff", "LEGENDARY": "#ffd86b",
}


def _initials(name: str, n: int = 2) -> str:
    words = [w for w in (name or "").strip().split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:n].upper()
    return "".join(w[0] for w in words[:n]).upper()


@router.get("/placeholder/hero/{code}.svg", response_class=Response, include_in_schema=False)
def placeholder_hero(
    code: str,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
    if tmpl is None:
        role_color = "#7d8a9c"
        frame_color = "#2d3847"
        initials = code[:2].upper() if code else "??"
    else:
        role_color = _ROLE_COLORS.get(str(tmpl.role), "#7d8a9c")
        frame_color = _RARITY_FRAMES.get(str(tmpl.rarity), "#2d3847")
        initials = _initials(tmpl.name)

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        f'<rect width="128" height="128" rx="12" ry="12" fill="#14202b" stroke="{frame_color}" stroke-width="3"/>'
        f'<circle cx="64" cy="50" r="26" fill="{role_color}" opacity="0.85"/>'
        f'<path d="M20 120 Q20 78 64 78 Q108 78 108 120 Z" fill="{role_color}" opacity="0.6"/>'
        f'<text x="64" y="60" text-anchor="middle" font-family="system-ui, sans-serif" '
        f'font-weight="800" font-size="22" fill="#0b0d10">{initials}</text>'
        '</svg>'
    )
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})
```

- [ ] **Step 3: Remove Jinja2 import and template dir from main.py (if applicable)**

Check `app/main.py` — if it imports `Jinja2Templates` or mounts the templates directory only for `ui.py`, those references can be removed. The `StaticFiles` mount at `/app/static` stays.

```bash
grep -n "Jinja2\|templates" app/main.py
```

Remove any lines that only served the HTMX templates if they exist. The StaticFiles mount must remain.

- [ ] **Step 4: Delete HTMX templates**

```bash
rm -rf app/templates/partials/
rm app/templates/shell.html app/templates/base.html
```

Email templates in `app/templates/email/` are untouched.

- [ ] **Step 5: Delete standalone JS and HTML files**

```bash
rm app/static/battle-setup.html
rm app/static/battle-phaser.html
rm app/static/battle-interactive.html
rm app/static/battle-replay.html
rm app/static/battle-pixi.html
rm app/static/team-picker.js
rm app/static/in-app-viewer.js
rm app/static/tutorial-hints.js
rm app/static/toast.js
rm app/static/sound.js
```

- [ ] **Step 6: Run the Python test suite**

```bash
pytest -x -q
```

Expected: all 634 tests pass. The API is untouched; only `ui.py` changed.

If tests fail due to imports removed from `ui.py` (e.g. if any test imports `ui._me_dict`): those are internal helpers — move the logic to the relevant JSON API router or inline it.

- [ ] **Step 7: Smoke test the cut-over SPA**

```bash
uvicorn app.main:app --port 8000
```

Open `http://localhost:8000/app/me` in a browser. Verify:
- The React SPA loads (not a 404 or old HTMX shell)
- Login works, currency bar populates
- Navigate to `/app/roster`, `/app/stages` — data loads
- Navigate to `/battle/setup` — hero + stage lists populate
- Full fight flow: pick heroes → fight → replay viewer → back to stages
- `GET http://localhost:8000/app/placeholder/hero/sentinel.svg` returns SVG (200 OK)

- [ ] **Step 8: Commit cutover**

```bash
git add app/routers/ui.py
git rm -r app/templates/partials/ app/templates/shell.html app/templates/base.html
git rm app/static/battle-setup.html app/static/battle-phaser.html app/static/battle-interactive.html app/static/battle-replay.html app/static/battle-pixi.html
git rm app/static/team-picker.js app/static/in-app-viewer.js app/static/tutorial-hints.js app/static/toast.js app/static/sound.js
git commit -m "feat(spa): HTMX cutover — delete partials + rewrite ui.py to SPA catch-all"
```

---

## Task 7: Full test run + frontend unit test suite

**Files:**
- Test: `frontend/src/components/BattleHUD.test.tsx` (already created)
- Test: `frontend/src/hooks/useBattleLog.test.tsx` (already created)
- Test: `frontend/src/api/battles.test.ts` (already created)

- [ ] **Step 1: Run the full frontend test suite**

```bash
cd frontend && npx vitest run
```

Expected: all component/hook/api tests pass. If any fail due to missing imports (e.g. `useToastStore` not exported from `store/ui`), add the export.

- [ ] **Step 2: Run Python tests one final time**

```bash
pytest -x -q
```

Expected: 634 tests pass.

- [ ] **Step 3: TypeScript type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: zero errors. Fix any type errors before marking this task complete.

- [ ] **Step 4: Production build check**

```bash
cd frontend && npm run build && echo "Build OK"
```

Expected: `app/static/spa/` populated, no errors, build exits 0.

- [ ] **Step 5: Commit final**

```bash
git add frontend/
git commit -m "test(spa): full test suite green post-cutover — vitest + pytest + tsc clean"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| `/battle/setup` route | Task 4 (BattleSetupRoute) |
| `/battle/:id/watch` + `/battle/:id/replay` | Task 5 (BattleReplayRoute — same component, two paths) |
| `/battle/:id/play` (interactive) | Task 5 (BattlePlayRoute) |
| `/battle/:id/replay` (replay) | Task 5 (BattleReplayRoute) |
| React `useRef` + `useEffect` canvas pattern | Task 5 (Phaser mount in BattleReplayRoute) |
| BattleHUD DOM overlay | Task 3 |
| HTMX layer deleted at cutover | Task 6 |
| `ui.py` swapped to SPA catch-all | Task 6 |
| `placeholder_hero` SVG endpoint kept | Task 6 (preserved in new ui.py) |
| Python 634-test suite stays green | Task 6 Step 6, Task 7 Step 2 |
| TypeScript types for battle resources | Task 1 (battle.ts) |
| Typed API wrappers | Task 1 (battles.ts) |
| TanStack Query hook for battle log | Task 2 (useBattleLog) |
| Interactive session state machine | Task 2 (useInteractiveSession) |

**Plan B note:** `BattlePlayRoute` intentionally uses a plain `<div>` background instead of a canvas. When DragonBones rigs land, swap the background `<div>` for a `<div ref={canvasRef}>` with a Pixi app mounted via `useEffect` — the `BattleHUD` overlay is unchanged.
