# System Integrity Frontend (Plan 3a — visible combat core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make System Integrity visible and playable in the interactive battle UI — render each unit's Integrity bar + Burnout meter, show the Crashed state, light a contextual **Delete** button, ship the drag-to-recycle-bin "DELETED" finisher ceremony, and react in Battle3D + toasts to the `INTEGRITY`/`CRASH`/`DELETED` events the backend already emits.

**Architecture:** Pure frontend. The backend (Plans 1+2, merged at `00bbe50`) already (a) puts `integrity`/`integrity_max`/`burnout`/`crashed` on every `UnitSnapshot`, (b) exposes `valid_delete_targets` + a `"delete"` key in `pending.actions`, (c) accepts `action_type="delete"` on the act endpoint, and (d) emits `INTEGRITY` / `CRASH` / `INTEGRITY_RESTORED` / `DELETED` log events from the resolver. This plan only syncs the TypeScript types to that contract and renders/uses it. No Python changes.

**Tech Stack:** React 18 + Vite + TypeScript, inline-style components, `vitest` + `@testing-library/react` (run with `bun test` from `frontend/`), Three.js Battle3D (`frontend/src/battle3d/`).

**Scope:** Plan 3a of the Plan 3 split. **Deferred to Plan 3b (separate plan):** Deleted bonus loot/multipliers, the perfect-finisher reward differential, universal-exploit banner, Composure gear, burnout-reset consumables, VIP multipliers, auto-perfect finisher QoL. In 3a the drag finisher is a pure cosmetic flourish — a perfect drag and a missed/auto drag both resolve to the same `action_type="delete"` backend call; the reward split is 3b.

**Design source:** `docs/superpowers/specs/battlebuttonsets.md` (§1 pillars, §2 button set, §5 locked decisions, §6 starting values).

**Backend contract this plan renders (already live — do NOT modify):**
- `UnitSnapshot`: `integrity: int`, `integrity_max: int` (0 = no bar — heroes), `burnout: int` (0–100), `crashed: bool`. (`app/schemas.py:515`)
- `PendingTurnOut`: `valid_delete_targets: list[str]`; `actions["delete"] = {"enabled": bool, "reason": str|None}`. (`app/schemas.py:538`, `app/combat.py:1109`)
- Act endpoint accepts `action_type="delete"` with `target_uid` = a uid from `valid_delete_targets`. (`app/interactive.py::ALLOWED_ACTION_TYPES`)
- Log events: `{"type":"INTEGRITY","unit":uid,...}`, `{"type":"CRASH","unit":uid,...}`, `{"type":"INTEGRITY_RESTORED","unit":uid,"integrity":n}`, `{"type":"DELETED","source":uid,"target":uid}`. (`app/combat.py:422/440/334/588`)

---

## Pre-flight (read before Task 1)

**WIP-branch overlap — resolve first.** The branch `wip/battle-hud-polish` (pushed) modifies the SAME files this plan touches: `BattleHUD.tsx`, `types/battle.ts`, `hooks/useInteractiveSession.ts`, `routes/battle/BattlePlayRoute.tsx`. It contains a real fix (passing `turnNumber` into the act request) plus reward-rendering polish. **Before starting, land the salvageable parts of that branch onto master** (at minimum the `useInteractiveSession` `turnNumber` wiring and the `rewards: Record<string, unknown>` widening) so this plan builds on top of it instead of colliding. If you skip that, expect a merge conflict in `BattleHUD.tsx` and `useInteractiveSession.ts` later. This plan assumes those two changes are already on master; if they are not, Task 1 still works (it touches different lines) but re-check `BattleHUD.tsx`'s `rewards` prop type before Task 7.

**Test command:** all frontend tests run from the `frontend/` directory with `bun test`. A single file: `bun test src/components/BattleHUD.test.tsx`. There is no per-test `-k`; rely on `describe`/`it` and run the whole file.

---

### Task 1: Sync TypeScript types to the backend System Integrity contract

**Files:**
- Modify: `frontend/src/types/battle.ts` (`CombatUnit`, `InteractivePending`)
- Modify: `frontend/src/api/battles.ts` (`ActionType`)
- Test: `frontend/src/types/battle.test.ts` (create)

- [ ] **Step 1: Write the failing test.** Create `frontend/src/types/battle.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import type { CombatUnit, InteractivePending } from './battle'
import type { ActionType } from '../api/battles'

describe('System Integrity types', () => {
  it('CombatUnit carries integrity/burnout/crashed', () => {
    const u: CombatUnit = {
      uid: 'B0', name: 'e', hp: 100, max_hp: 100, atk: 1, def: 1, spd: 1, dead: false,
      integrity: 0, integrity_max: 150, burnout: 40, crashed: true,
    }
    expect(u.integrity_max).toBe(150)
    expect(u.crashed).toBe(true)
    expect(u.burnout).toBe(40)
  })

  it('InteractivePending exposes valid_delete_targets and a delete action', () => {
    const p: InteractivePending = {
      actor_uid: 'A0',
      valid_delete_targets: ['B0'],
      actions: {
        attack: { enabled: true, reason: null },
        skill: { enabled: false, reason: 'on cooldown' },
        limit: { enabled: false, reason: 'gauge not full' },
        defend: { enabled: true, reason: null },
        delete: { enabled: true, reason: null },
      },
    }
    expect(p.valid_delete_targets).toEqual(['B0'])
    expect(p.actions?.delete.enabled).toBe(true)
  })

  it('ActionType includes delete', () => {
    const a: ActionType = 'delete'
    expect(a).toBe('delete')
  })
})
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun test src/types/battle.test.ts`
Expected: FAIL — `delete` not assignable to `ActionType`; `integrity`/`crashed`/`valid_delete_targets` not on the types.

- [ ] **Step 3: Add the fields.** In `frontend/src/types/battle.ts`, extend the `CombatUnit` interface (after `limit_gauge_max?: number`):

```typescript
  /** System Integrity (weakness-break). integrity_max === 0 means no bar (heroes). */
  integrity?: number
  integrity_max?: number
  burnout?: number
  crashed?: boolean
```

In the same file, extend `InteractivePending`: add the field and widen the `actions` key union to include `'delete'`:

```typescript
  /** Enemy uids the acting unit may Delete this turn (Crashed + threshold). */
  valid_delete_targets?: string[]
  /** Phase A + System Integrity: per-action availability for the HUD action bar. */
  actions?: Record<'attack' | 'skill' | 'limit' | 'defend' | 'delete', { enabled: boolean; reason: string | null }>
```

In `frontend/src/api/battles.ts`, change the `ActionType` union:

```typescript
export type ActionType = 'attack' | 'skill' | 'limit' | 'defend' | 'delete'
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun test src/types/battle.test.ts`
Expected: PASS.

- [ ] **Step 5: Typecheck the whole app** (the widened `actions` Record now requires a `delete` key everywhere an `actions` literal is built — catch fallout): `cd frontend && bun run build` (or `bunx tsc --noEmit` if defined). Fix any object literals that construct `pending.actions` without a `delete` key by adding `delete: { enabled: false, reason: null }`. Search: `grep -rn "actions:" frontend/src --include=*.tsx --include=*.ts`.
Expected: clean typecheck.

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/types/battle.ts frontend/src/api/battles.ts frontend/src/types/battle.test.ts
git commit -m "feat(combat-ui): TS types for integrity/burnout/crash + delete action"
```

---

### Task 2: Render the Integrity bar + Burnout meter on each unit card

**Files:**
- Modify: `frontend/src/components/BattleHUD.tsx` (`UnitCard`, ~lines 256-266 where the HP bar renders)
- Test: `frontend/src/components/BattleHUD.test.tsx`

**Design (spec §1A, §1C, §6):** Integrity bar sits directly under the HP bar, only when `integrity_max > 0` (enemies). Burnout meter sits under that, only when `burnout` is defined and `> 0`, color-graded: ≤25 green (sharp), ≥75 red (overheated), else amber. Mirror the existing 4px HP-bar pattern.

- [ ] **Step 1: Write the failing test.** Add to `frontend/src/components/BattleHUD.test.tsx` (extend `makeUnit` calls inline). Add inside the existing `describe('BattleHUD', ...)`:

```typescript
  it('renders an integrity bar for enemies with a bar and a burnout meter', () => {
    const enemy: CombatUnit = {
      uid: 'enemy-1', name: 'enemy-1', hp: 60, max_hp: 120, atk: 1, def: 1, spd: 1,
      dead: false, integrity: 75, integrity_max: 150, burnout: 80,
    }
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[enemy]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />,
    )
    expect(screen.getByTestId('integrity-enemy-1')).toBeTruthy()
    expect(screen.getByTestId('burnout-enemy-1')).toBeTruthy()
  })

  it('omits the integrity bar for heroes (integrity_max 0)', () => {
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />,
    )
    expect(screen.queryByTestId('integrity-hero-1')).toBeNull()
  })
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun test src/components/BattleHUD.test.tsx`
Expected: FAIL — no element with testid `integrity-enemy-1`.

- [ ] **Step 3: Implement.** In `BattleHUD.tsx`, immediately after the HP-value `<div>` (`{unit.hp} / {unit.max_hp}`, ~line 266) inside `UnitCard`, insert:

```tsx
{(unit.integrity_max ?? 0) > 0 && (
  <div data-testid={`integrity-${unit.uid}`} style={{ marginTop: 3 }}>
    <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
      <div
        style={{
          width: `${Math.max(0, Math.min(1, (unit.integrity ?? 0) / (unit.integrity_max || 1))) * 100}%`,
          height: '100%',
          background: unit.crashed ? '#e85a78' : '#5ad8ff',
          transition: 'width 0.3s',
        }}
      />
    </div>
    <div style={{ fontSize: 9, color: 'var(--color-muted)', letterSpacing: '0.12em', marginTop: 1 }}>
      {unit.crashed ? 'CRASHED' : 'INTEGRITY'}
    </div>
  </div>
)}
{(unit.burnout ?? 0) > 0 && (
  <div data-testid={`burnout-${unit.uid}`} style={{ marginTop: 3 }}>
    <div style={{ height: 3, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
      <div
        style={{
          width: `${Math.max(0, Math.min(100, unit.burnout ?? 0))}%`,
          height: '100%',
          background:
            (unit.burnout ?? 0) >= 75 ? '#ff5a4d'
            : (unit.burnout ?? 0) <= 25 ? '#5ad8a3'
            : '#e8a35a',
          transition: 'width 0.3s',
        }}
      />
    </div>
  </div>
)}
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun test src/components/BattleHUD.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/components/BattleHUD.tsx frontend/src/components/BattleHUD.test.tsx
git commit -m "feat(combat-ui): integrity bar + burnout meter on unit cards"
```

---

### Task 3: Crashed visual state on the unit card

**Files:**
- Modify: `frontend/src/components/BattleHUD.tsx` (`UnitCard` root style + name)
- Test: `frontend/src/components/BattleHUD.test.tsx`

**Design (spec §1A):** a Crashed enemy reads as "glitched" — a crimson border tint + a `CRASHED` tag near its name. (The bar already turns crimson from Task 2.)

- [ ] **Step 1: Write the failing test.** Add to `BattleHUD.test.tsx`:

```typescript
  it('tags a crashed unit', () => {
    const enemy: CombatUnit = {
      uid: 'enemy-9', name: 'glitchwraith', hp: 20, max_hp: 120, atk: 1, def: 1, spd: 1,
      dead: false, integrity: 0, integrity_max: 150, crashed: true,
    }
    render(
      <BattleHUD
        teamA={[]} teamB={[enemy]} onAct={undefined} pendingActorUid={null}
        validTargets={[]} acting={false} done={false} rewards={null} onClose={() => {}}
      />,
    )
    expect(screen.getByTestId('crashed-tag-enemy-9')).toBeTruthy()
  })
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun test src/components/BattleHUD.test.tsx`
Expected: FAIL — no `crashed-tag-enemy-9`.

- [ ] **Step 3: Implement.** In `UnitCard`, find the unit name `<div>` (the `fontSize: 11` name element, ~line 240). Wrap it so a crashed unit shows a tag. Replace the name `<div>` with:

```tsx
<div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text)' }}>{unit.name}</div>
  {unit.crashed && (
    <span
      data-testid={`crashed-tag-${unit.uid}`}
      style={{
        fontSize: 8, fontWeight: 800, letterSpacing: '0.14em', color: '#e85a78',
        border: '1px solid #e85a78', borderRadius: 3, padding: '0 3px',
        fontFamily: 'JetBrains Mono, ui-monospace, monospace',
      }}
    >
      CRASHED
    </span>
  )}
</div>
```

(If the existing name `<div>` has different inline styles, preserve them on the inner name `<div>` — only add the flex wrapper + tag.) Then add a crashed tint to the `UnitCard` root container style — locate the card's outermost `<div style={{ ... }}>` and append a conditional `boxShadow`:

```tsx
boxShadow: unit.crashed ? '0 0 0 1px #e85a78, 0 0 12px rgba(232,90,120,0.35)' : undefined,
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun test src/components/BattleHUD.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/components/BattleHUD.tsx frontend/src/components/BattleHUD.test.tsx
git commit -m "feat(combat-ui): crashed unit visual state (tag + glow)"
```

---

### Task 4: The contextual Delete button in the action bar

**Files:**
- Modify: `frontend/src/components/BattleHUD.tsx` (`ActionBar`, button row ~lines 369-378; `Button` handler ~292-301)
- Test: `frontend/src/components/BattleHUD.test.tsx`

**Design (spec §2):** Delete is hidden unless `pending.actions.delete.enabled` is true (i.e. a valid Delete target exists). It is crimson (`#e85a78`). Clicking it arms the delete action (target chosen next) — like attack/skill, it needs a target (the Crashed enemy). It does NOT fire immediately.

- [ ] **Step 1: Write the failing test.** Add to `BattleHUD.test.tsx`:

```typescript
  const pendingWithDelete: InteractivePending = {
    actor_uid: 'hero-1',
    turn_number: 1,
    enemies: [{ uid: 'enemy-1', name: 'enemy-1', hp: 20, max_hp: 120 }],
    valid_delete_targets: ['enemy-1'],
    actions: {
      attack: { enabled: true, reason: null },
      skill: { enabled: false, reason: 'no skill' },
      limit: { enabled: false, reason: 'gauge not full' },
      defend: { enabled: true, reason: null },
      delete: { enabled: true, reason: null },
    },
  }

  it('shows the Delete button only when a delete target exists', () => {
    const onSelectAction = vi.fn()
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[makeUnit('enemy-1', 20, 120)]}
        onAct={() => {}}
        onSelectAction={onSelectAction}
        pendingActorUid="hero-1"
        pending={pendingWithDelete}
        selectedAction="attack"
        validTargets={['enemy-1']}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />,
    )
    const del = screen.getByRole('button', { name: /delete/i })
    fireEvent.click(del)
    expect(onSelectAction).toHaveBeenCalledWith('delete')
  })

  it('hides the Delete button when no delete target exists', () => {
    const noDelete: InteractivePending = {
      ...pendingWithDelete,
      valid_delete_targets: [],
      actions: { ...pendingWithDelete.actions!, delete: { enabled: false, reason: 'no crashed target' } },
    }
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[makeUnit('enemy-1', 90, 120)]}
        onAct={() => {}}
        onSelectAction={() => {}}
        pendingActorUid="hero-1"
        pending={noDelete}
        selectedAction="attack"
        validTargets={['enemy-1']}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />,
    )
    expect(screen.queryByRole('button', { name: /delete/i })).toBeNull()
  })
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun test src/components/BattleHUD.test.tsx`
Expected: FAIL — no Delete button.

- [ ] **Step 3: Implement.** In `ActionBar`:

(a) The `Button` component colors by `kind`. Add a crimson color for `'delete'`. Find the color map/ternary (~line 303-336, where `'#e8a35a'`/`'#9b88ff'`/etc. are chosen) and add the `delete` case, e.g.:

```tsx
const color =
  kind === 'limit' ? '#e8a35a'
  : kind === 'skill' ? '#9b88ff'
  : kind === 'defend' ? '#5ad8a3'
  : kind === 'delete' ? '#e85a78'
  : '#00e0d0'
```

(b) The button click handler (`handle(kind)`, ~line 292-301) decides which actions fire immediately vs arm-then-target. `delete` must arm-then-target (like `attack`/`skill`). Ensure the branch that calls `onSelectAction?.(kind)` (rather than `onAct('', kind)`) includes `'delete'`. If the logic is "limit and defend fire immediately, others arm", `delete` already falls into the arm branch — verify and leave; otherwise add `kind === 'delete'` to the arm condition.

(c) Render the button conditionally after the Defend button (~line 377):

```tsx
{pending.actions?.delete?.enabled && (
  <Button kind="delete" label="Delete" sub="bin it" />
)}
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun test src/components/BattleHUD.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/components/BattleHUD.tsx frontend/src/components/BattleHUD.test.tsx
git commit -m "feat(combat-ui): contextual Delete action button"
```

---

### Task 5: Route the delete action through the play route

**Files:**
- Modify: `frontend/src/routes/battle/BattlePlayRoute.tsx` (validTargets computation ~line 141/158; the `executeAction` wiring)
- Test: none new (covered by Task 4 unit test + the manual smoke in Task 8). This task is integration wiring; verify by build + existing route tests.

**Design:** When the player has armed `delete` (`selectedAction === 'delete'`), the set of clickable targets must be `pending.valid_delete_targets` (only Crashed-and-eligible enemies), NOT the normal attack target list. And the act call must send `action_type='delete'`.

- [ ] **Step 1: Read context.** Open `frontend/src/routes/battle/BattlePlayRoute.tsx`. Find: `selectedAction` state, `executeAction` (the function passed as `onAct`), and the two places `validTargets` is computed (`pending?.valid_targets ?? pending?.enemies?.map(e => e.uid) ?? []`).

- [ ] **Step 2: Implement target-set switching.** Introduce a derived `currentValidTargets` near where `pending` is read:

```tsx
const currentValidTargets =
  selectedAction === 'delete'
    ? (pending?.valid_delete_targets ?? [])
    : (pending?.valid_targets ?? pending?.enemies?.map((e) => e.uid) ?? [])
```

Replace BOTH inline `validTargets={pending?.valid_targets ?? ...}` props (the BattleHUD prop and the Battle3D prop) with `validTargets={currentValidTargets}`. Also use `currentValidTargets` in the auto-play loop's `targets` computation if you want auto-play to never accidentally pick delete (it shouldn't — auto-play keeps `selectedAction` irrelevant since it calls `act(bestUid)` with no action type; leave auto-play on the attack target set: keep its own `pending.valid_targets ?? pending.enemies...` and do NOT switch it to delete).

- [ ] **Step 3: Implement the act call.** Confirm `executeAction` forwards `selectedAction` as the action type to `act(targetUid, selectedAction)`. If `executeAction` currently hardcodes or omits the action type, change it to pass `selectedAction`:

```tsx
const executeAction = (targetUid: string) => {
  setAutoPlay(false)
  act(targetUid, selectedAction)
}
```

(Adapt to the real signature — the goal is: clicking a Crashed enemy while `selectedAction==='delete'` calls `act(uid, 'delete')`.)

- [ ] **Step 4: Verify build + route tests.** `cd frontend && bun run build && bun test src/routes/battle`
Expected: clean build; existing battle-route tests pass (if none exist for this route, build success is the gate).

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/routes/battle/BattlePlayRoute.tsx
git commit -m "feat(combat-ui): route delete action to crashed targets"
```

---

### Task 6: Toasts + Battle3D reactions for INTEGRITY / CRASH / DELETED

**Files:**
- Modify: `frontend/src/routes/battle/BattlePlayRoute.tsx` (the `last_event` toast `useEffect`, ~lines 94-110)
- Modify: `frontend/src/battle3d/animationDriver.ts` (`CombatEvent` union ~lines 14-22; `handleEvent` ~lines 35-99)
- Test: `frontend/src/battle3d/animationDriver.test.ts` (create)

**Design (spec §1A/§1B):** `CRASH` → target plays a stagger/flash + "Crashed!" toast. `DELETED` → target fades out + a deadpan "DELETED" toast. `INTEGRITY` is high-frequency (every weakness hit) — NO toast (too noisy); optionally a subtle flash, but keep it cheap.

- [ ] **Step 1: Write the failing test.** Create `frontend/src/battle3d/animationDriver.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { handleEvent } from './animationDriver'
import type { UnitRig } from './animationDriver'

function fakeRig(uid: string): UnitRig & { calls: string[] } {
  const calls: string[] = []
  return {
    uid, archetype: 'knight', availableClips: ['hit', 'die'], calls,
    play: (c: string) => calls.push(`play:${c}`),
    flashWhite: () => calls.push('flashWhite'),
    floatDamageNumber: () => calls.push('float'),
    fade: (o: number) => calls.push(`fade:${o}`),
  }
}

describe('handleEvent — system integrity', () => {
  it('CRASH staggers and flashes the target', () => {
    const rig = fakeRig('B0')
    const rigs = new Map<string, UnitRig>([['B0', rig]])
    handleEvent({ type: 'CRASH', unit: 'B0' }, rigs)
    expect(rig.calls).toContain('flashWhite')
  })

  it('DELETED fades the target out', () => {
    const rig = fakeRig('B0')
    const rigs = new Map<string, UnitRig>([['B0', rig]])
    handleEvent({ type: 'DELETED', source: 'A0', target: 'B0' }, rigs)
    expect(rig.calls.some((c) => c.startsWith('fade:'))).toBe(true)
  })
})
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun test src/battle3d/animationDriver.test.ts`
Expected: FAIL — `CRASH`/`DELETED` fall through to the no-op default (no `flashWhite`/`fade` calls).

- [ ] **Step 3: Implement the driver.** In `animationDriver.ts`, extend the `CombatEvent` union (add before the catch-all `{ type: string; ... }` member):

```typescript
  | { type: "INTEGRITY"; unit?: string; target_uid?: string; amount?: number }
  | { type: "CRASH"; unit?: string; target_uid?: string }
  | { type: "DELETED"; source?: string; target?: string; target_uid?: string }
```

In `handleEvent`, add handlers (place near the `DEATH` handler):

```typescript
  if (event.type === "CRASH") {
    const uid = (event.target_uid ?? event.unit) as string | undefined;
    const victim = uid ? rigs.get(uid) : undefined;
    if (victim) {
      playCanonical(victim, "hit");
      victim.flashWhite();
    }
    return;
  }
  if (event.type === "DELETED") {
    const uid = (event.target_uid ?? event.target) as string | undefined;
    const victim = uid ? rigs.get(uid) : undefined;
    if (victim) {
      playCanonical(victim, "die");
      victim.fade(0.0);
    }
    return;
  }
```

(`playCanonical` is the existing helper used by the DAMAGE/DEATH handlers — reuse it; "hit"/"die" are already in the canonical clip set.)

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun test src/battle3d/animationDriver.test.ts`
Expected: PASS.

- [ ] **Step 5: Add the toasts.** In `BattlePlayRoute.tsx`, in the `last_event` toast `useEffect`, add branches alongside the existing `SPECIAL`/`LIMIT_BREAK`/`DEFEND` cases:

```tsx
} else if (kind === 'CRASH') {
  toast.error(`${eventActor} crashed`)
} else if (kind === 'DELETED') {
  const tgtUid = String(event.target ?? event.target_uid ?? '')
  const tgtName = tgtUid ? (nameByUid[tgtUid] ?? 'target') : 'target'
  toast.success(`${tgtName} — DELETED`)
}
```

(Do NOT add an `INTEGRITY` branch — it fires on every weakness hit and would spam.)

- [ ] **Step 6: Verify build + driver test.** `cd frontend && bun run build && bun test src/battle3d/animationDriver.test.ts`
Expected: clean build; PASS.

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/battle3d/animationDriver.ts frontend/src/battle3d/animationDriver.test.ts frontend/src/routes/battle/BattlePlayRoute.tsx
git commit -m "feat(combat-ui): crash/deleted Battle3D reactions + toasts"
```

---

### Task 7: The recycle-bin drag finisher overlay (the flourish)

**Files:**
- Create: `frontend/src/components/RecycleBinFinisher.tsx`
- Create: `frontend/src/components/RecycleBinFinisher.css`
- Create: `frontend/src/components/RecycleBinFinisher.test.tsx`
- Modify: `frontend/src/components/BattleHUD.tsx` (mount the overlay when a delete is armed + a Crashed unit is clicked)

**Design (spec §1B, §5.4, §5.8, §5.9, §6):** When the player commits a Delete, instead of firing instantly, show a brief full-screen ceremony: the Crashed enemy's portrait/marker becomes draggable, a recycle-bin icon appears at a **randomized position within a safe zone** (inset from edges, off the action bar), and the player drags the marker into the bin within a ~2.5s window. Dropping it in the bin → `DELETED` callout + `onPerfect()`. Window expiry, a miss, or release outside the bin → `onPlain()` (auto-resolve). **Both callbacks ultimately trigger the same `action_type='delete'` act call** (the bonus differential is Plan 3b); for 3a, `onPerfect` and `onPlain` can be the same handler — the overlay just adds ceremony. Touch + mouse via Pointer Events. Accessible fallback: the overlay also renders a plain "Delete" button (keyboard/screen-reader path) that calls the same resolve.

- [ ] **Step 1: Write the failing test.** Create `frontend/src/components/RecycleBinFinisher.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { RecycleBinFinisher } from './RecycleBinFinisher'

describe('RecycleBinFinisher', () => {
  it('renders the target name and a bin drop zone', () => {
    render(
      <RecycleBinFinisher
        targetUid="B0" targetName="glitchwraith"
        windowMs={2500} onResolve={() => {}}
      />,
    )
    expect(screen.getByText(/glitchwraith/i)).toBeTruthy()
    expect(screen.getByTestId('recycle-bin')).toBeTruthy()
    expect(screen.getByTestId('finisher-draggable')).toBeTruthy()
  })

  it('auto-resolves (plain) when the window elapses', () => {
    vi.useFakeTimers()
    const onResolve = vi.fn()
    render(
      <RecycleBinFinisher
        targetUid="B0" targetName="glitchwraith"
        windowMs={2500} onResolve={onResolve}
      />,
    )
    act(() => { vi.advanceTimersByTime(2600) })
    expect(onResolve).toHaveBeenCalledWith({ targetUid: 'B0', perfect: false })
    vi.useRealTimers()
  })

  it('resolves perfect via the accessible button', () => {
    const onResolve = vi.fn()
    render(
      <RecycleBinFinisher
        targetUid="B0" targetName="glitchwraith"
        windowMs={2500} onResolve={onResolve}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /delete now/i }))
    expect(onResolve).toHaveBeenCalledWith({ targetUid: 'B0', perfect: true })
  })
})
```

- [ ] **Step 2: Run to verify it fails.** `cd frontend && bun test src/components/RecycleBinFinisher.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the component.** Create `frontend/src/components/RecycleBinFinisher.tsx`:

```tsx
import { useEffect, useRef, useState, useCallback } from 'react'
import './RecycleBinFinisher.css'

export interface FinisherResult {
  targetUid: string
  perfect: boolean
}

interface Props {
  targetUid: string
  targetName: string
  windowMs?: number
  onResolve: (r: FinisherResult) => void
}

/** Deterministic-enough bin placement without Math.random in render:
 *  derive from the uid so it varies per target but is stable across re-renders. */
function binPosition(uid: string): { topPct: number; leftPct: number } {
  let h = 0
  for (let i = 0; i < uid.length; i++) h = (h * 31 + uid.charCodeAt(i)) >>> 0
  // Safe zone: 15-75% vertical (off the bottom action bar), 10-80% horizontal.
  const topPct = 15 + (h % 60)
  const leftPct = 10 + ((h >> 8) % 70)
  return { topPct, leftPct }
}

export function RecycleBinFinisher({ targetUid, targetName, windowMs = 2500, onResolve }: Props) {
  const resolvedRef = useRef(false)
  const binRef = useRef<HTMLDivElement | null>(null)
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null)
  const pos = binPosition(targetUid)

  const resolve = useCallback((perfect: boolean) => {
    if (resolvedRef.current) return
    resolvedRef.current = true
    onResolve({ targetUid, perfect })
  }, [onResolve, targetUid])

  useEffect(() => {
    const t = window.setTimeout(() => resolve(false), windowMs)
    return () => window.clearTimeout(t)
  }, [resolve, windowMs])

  const onPointerMove = (e: React.PointerEvent) => {
    if (dragPos === null) return
    setDragPos({ x: e.clientX, y: e.clientY })
  }
  const onPointerUp = (e: React.PointerEvent) => {
    if (dragPos === null) return
    const bin = binRef.current?.getBoundingClientRect()
    const hit = bin
      ? e.clientX >= bin.left && e.clientX <= bin.right && e.clientY >= bin.top && e.clientY <= bin.bottom
      : false
    setDragPos(null)
    if (hit) resolve(true)
    // miss: leave the window running — they can retry until it expires (plain on timeout)
  }

  return (
    <div
      className="recycle-finisher"
      role="dialog"
      aria-modal="true"
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <div className="recycle-finisher-prompt">Drag {targetName} to the bin</div>
      <div
        data-testid="finisher-draggable"
        className="recycle-finisher-target"
        style={dragPos ? { left: dragPos.x, top: dragPos.y } : undefined}
        onPointerDown={(e) => { setDragPos({ x: e.clientX, y: e.clientY }); (e.target as Element).setPointerCapture?.(e.pointerId) }}
      >
        {targetName}
      </div>
      <div
        data-testid="recycle-bin"
        ref={binRef}
        className="recycle-finisher-bin"
        style={{ top: `${pos.topPct}%`, left: `${pos.leftPct}%` }}
      >
        🗑
      </div>
      <button className="recycle-finisher-accessible" onClick={() => resolve(true)}>
        Delete now
      </button>
    </div>
  )
}
```

Create `frontend/src/components/RecycleBinFinisher.css`:

```css
.recycle-finisher {
  position: fixed;
  inset: 0;
  z-index: 1600;
  background: radial-gradient(120% 100% at 50% 0%, rgba(232, 90, 120, 0.12), transparent 50%), rgba(3, 7, 14, 0.82);
  touch-action: none;
}
.recycle-finisher-prompt {
  position: absolute;
  top: 8%;
  left: 50%;
  transform: translateX(-50%);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
  letter-spacing: 0.16em;
  color: #e85a78;
  text-transform: uppercase;
}
.recycle-finisher-target {
  position: absolute;
  top: 80%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 10px 16px;
  border: 1px solid #e85a78;
  border-radius: 8px;
  background: rgba(232, 90, 120, 0.15);
  color: #fff;
  font-weight: 700;
  cursor: grab;
  user-select: none;
  touch-action: none;
}
.recycle-finisher-bin {
  position: absolute;
  transform: translate(-50%, -50%);
  font-size: 44px;
  filter: drop-shadow(0 0 8px rgba(232, 90, 120, 0.6));
}
.recycle-finisher-accessible {
  position: absolute;
  bottom: 6%;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 18px;
  border: 1px solid #e85a78;
  border-radius: 6px;
  background: transparent;
  color: #e85a78;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.18em;
  cursor: pointer;
}
```

- [ ] **Step 4: Run to verify it passes.** `cd frontend && bun test src/components/RecycleBinFinisher.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Mount it from BattleHUD.** In `BattleHUD.tsx`, add state for an active finisher and show the overlay when the player commits a delete. The cleanest seam: BattleHUD already routes clicks through `onAct(targetUid, actionType)`. Intercept the delete case — when `selectedAction === 'delete'` and a target is clicked, instead of calling `onAct` immediately, set finisher state; the overlay's `onResolve` then calls `onAct(targetUid, 'delete')`. Add near the top of the `BattleHUD` function body:

```tsx
const [finisher, setFinisher] = useState<{ uid: string; name: string } | null>(null)
```

Wrap the click-to-act path: find where a unit click calls `onAct(uid, selectedAction)` (the target-click handler). Change it to:

```tsx
const commitTarget = (uid: string) => {
  if (selectedAction === 'delete') {
    const u = [...teamA, ...teamB].find((x) => x.uid === uid)
    setFinisher({ uid, name: u?.name ?? uid })
    return
  }
  onAct?.(uid, selectedAction)
}
```

Use `commitTarget` wherever the unit-click currently calls `onAct(uid, ...)`. Then render the overlay (near the end of the returned JSX, before the closing fragment):

```tsx
{finisher && (
  <RecycleBinFinisher
    targetUid={finisher.uid}
    targetName={finisher.name}
    onResolve={({ targetUid }) => {
      setFinisher(null)
      onAct?.(targetUid, 'delete')
    }}
  />
)}
```

Add the import at the top: `import { RecycleBinFinisher } from './RecycleBinFinisher'`. (Note: `perfect` is intentionally ignored in 3a — both paths fire the same `onAct`. Plan 3b will branch on it.)

- [ ] **Step 6: Run the BattleHUD tests + build.** `cd frontend && bun test src/components/BattleHUD.test.tsx && bun run build`
Expected: PASS + clean build. (If a Task 4 test now goes through `commitTarget`, confirm the delete-arm test still asserts `onSelectAction('delete')` on the button click — that path is unchanged; only the subsequent target click is intercepted.)

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/components/RecycleBinFinisher.tsx frontend/src/components/RecycleBinFinisher.css frontend/src/components/RecycleBinFinisher.test.tsx frontend/src/components/BattleHUD.tsx
git commit -m "feat(combat-ui): recycle-bin drag finisher ceremony"
```

---

### Task 8: Full frontend regression + live smoke

**Files:** none (verification only)

- [ ] **Step 1: Full frontend suite.** `cd frontend && bun test 2>&1 | tail -20`
Expected: all green (the 84 existing + the new type/HUD/driver/finisher tests). If a pre-existing snapshot/test asserts the exact unit-card DOM and now breaks because of the integrity/burnout bars, update it to accommodate the new elements (do not remove the bars).

- [ ] **Step 2: Production build.** `cd frontend && bun run build`
Expected: clean TypeScript + Vite build. The build output lands in `app/static/spa/` (committed — per CLAUDE.md). Stage the regenerated `app/static/spa/` assets in the final commit.

- [ ] **Step 3: Live smoke (recommended).** Start the backend (`uv run uvicorn app.main:app --port 8000`), open `http://127.0.0.1:8000/app/`, run an interactive stage, and confirm: enemy cards show an Integrity bar; hitting an on-faction weakness drains it; zeroing it flips the card to Crashed (crimson) + a "crashed" toast; a Delete button appears; committing Delete shows the recycle-bin overlay; dropping into the bin (or the 2.5s auto) fires a "DELETED" toast and removes the enemy. Heroes show no Integrity bar.

- [ ] **Step 4: Final commit (built assets).**

```bash
git add app/static/spa
git commit -m "build(spa): rebuild with system integrity battle HUD" --allow-empty
```

---

## Self-review notes

- **Spec coverage:** §1A Integrity bar (T2) + Crash visual (T3); §1C Burnout meter (T2); §2 Delete button contextual gating (T4) + routing (T5); §1B drag-to-recycle-bin finisher, randomized bin, in-clock window, auto-resolve, accessible button path (T7); Battle3D crash/delete reaction + toasts (T6). **Deferred to 3b (explicitly):** bonus loot/multipliers + perfect-vs-plain reward differential (T7 ignores `perfect`), and all monetization hooks (§7). The `perfect` flag is plumbed through `FinisherResult` so 3b can branch on it without rework.
- **No backend changes:** every field/event this plan renders already ships on master (`00bbe50`). Verified: `UnitSnapshot` integrity/burnout/crashed, `valid_delete_targets`, `actions["delete"]`, `ALLOWED_ACTION_TYPES` delete, and the `INTEGRITY`/`CRASH`/`DELETED` log events.
- **Type consistency:** `ActionType` gains `'delete'` (T1) and is used consistently in T4/T5/T7; `FinisherResult` (`{targetUid, perfect}`) defined in T7 and asserted in its tests; `UnitRig` reused from the existing `animationDriver.ts` (not redefined).
- **No `Math.random` in render:** bin position is derived from the uid hash (stable per target, varied across targets) — avoids the project-wide rule against `Math.random`/`Date.now` in deterministic paths and keeps tests stable.
- **WIP-branch hazard:** flagged in Pre-flight — `wip/battle-hud-polish` edits the same four files; land its `turnNumber` fix + `rewards` widening first to avoid conflicts.
- **Accessibility:** the finisher always offers a non-drag "Delete now" button; auto-battle/sweep never mounts the overlay (it calls `act(uid)` directly, never arming `selectedAction='delete'` through the HUD).
