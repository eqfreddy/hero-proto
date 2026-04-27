# SPA Rewrite — Plan 1: Scaffold

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the React SPA project (`frontend/`) with auth, API client, TanStack Query, Zustand stores, design tokens, and the app shell (NavBar + CurrencyBar + routing skeleton). End state: `npm run dev` serves a running app at localhost:5173 that authenticates against the live FastAPI backend and shows the full nav.

**Architecture:** Vite project in `frontend/` at project root. Vite proxy routes all `/me`, `/heroes`, etc. calls to FastAPI on :8000. Zustand stores hold JWT + sound + UI state. TanStack QueryClient wraps the app. Shell layout renders NavBar + CurrencyBar + `<Outlet>` for child routes. Route stubs exist for all 15 app tabs so navigation works before content is built.

**Tech Stack:** React 18, TypeScript 5 (strict), Vite 5, React Router v6, TanStack Query v5, Zustand v5, vite-plugin-pwa, Vitest 2 + React Testing Library 16 + jsdom

---

## File map

**Create:**
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles/tokens.css`
- `frontend/src/styles/global.css`
- `frontend/src/types/index.ts`
- `frontend/src/store/auth.ts`
- `frontend/src/store/sound.ts`
- `frontend/src/store/ui.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/me.ts`
- `frontend/src/hooks/useMe.ts`
- `frontend/src/components/Layout/Shell.tsx`
- `frontend/src/components/Layout/NavBar.tsx`
- `frontend/src/components/Layout/CurrencyBar.tsx`
- `frontend/src/components/Layout/BellPopover.tsx`
- `frontend/src/components/Layout/SoundPopover.tsx`
- `frontend/src/components/EmptyState.tsx`
- `frontend/src/components/SkeletonGrid.tsx`
- `frontend/src/routes/Login.tsx`
- `frontend/src/routes/Stub.tsx` ← shared stub for unbuilt tabs
- `frontend/src/test/setup.ts`
- `frontend/src/test/auth.test.ts`
- `frontend/src/test/apiClient.test.ts`
- `frontend/src/test/shell.test.tsx`

**Modify:**
- `.gitignore` — add `app/static/spa/`

---

### Task 1: Init Vite project + install dependencies

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Modify: `.gitignore`

- [ ] **Step 1: Scaffold the Vite project**

Run from the project root (`hero-proto/`):
```bash
npm create vite@latest frontend -- --template react-ts
```
Expected: `frontend/` directory created with `src/App.tsx`, `src/main.tsx`, `package.json`, `vite.config.ts`, `tsconfig.json`.

- [ ] **Step 2: Install runtime dependencies**

```bash
cd frontend && npm install react-router-dom@^6.26 @tanstack/react-query@^5.56 zustand@^5.0 vite-plugin-pwa@^0.20
```

- [ ] **Step 3: Install dev dependencies**

```bash
npm install -D vitest@^2.1 @testing-library/react@^16 @testing-library/jest-dom@^6.5 @testing-library/user-event@^14.5 jsdom@^25 @vitest/coverage-v8
```

- [ ] **Step 4: Replace vite.config.ts**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'hero-proto',
        short_name: 'hero-proto',
        theme_color: '#0b0d10',
        background_color: '#0b0d10',
        display: 'standalone',
        start_url: '/app/',
        scope: '/app/',
        icons: [
          { src: '/app/static/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/app/static/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
    }),
  ],
  base: '/app/static/spa/',
  build: {
    outDir: '../app/static/spa',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/me': 'http://localhost:8000',
      '/heroes': 'http://localhost:8000',
      '/battles': 'http://localhost:8000',
      '/raids': 'http://localhost:8000',
      '/guilds': 'http://localhost:8000',
      '/stages': 'http://localhost:8000',
      '/summon': 'http://localhost:8000',
      '/shop': 'http://localhost:8000',
      '/arena': 'http://localhost:8000',
      '/friends': 'http://localhost:8000',
      '/dm': 'http://localhost:8000',
      '/daily': 'http://localhost:8000',
      '/story': 'http://localhost:8000',
      '/achievements': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/crafting': 'http://localhost:8000',
      '/notifications': 'http://localhost:8000',
      '/liveops': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/placeholder': 'http://localhost:8000',
      '/gear': 'http://localhost:8000',
      '/inventory': 'http://localhost:8000',
      '/admin': { target: 'http://localhost:8000', rewrite: p => p },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
```

- [ ] **Step 5: Replace tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 6: Replace tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 7: Replace index.html**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#0b0d10" />
    <title>hero-proto</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Add app/static/spa/ to .gitignore**

Add to the root `.gitignore`:
```
app/static/spa/
```

- [ ] **Step 9: Verify dev server starts**

```bash
cd frontend && npm run dev
```
Expected: `VITE v5.x ready at http://localhost:5173/` with no TypeScript errors.

- [ ] **Step 10: Commit**

```bash
cd .. && git add frontend/ .gitignore
git commit -m "feat: scaffold Vite React TS SPA project with proxy config"
```

---

### Task 2: Design tokens + global styles

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`

- [ ] **Step 1: Create tokens.css**

```css
/* frontend/src/styles/tokens.css */
:root {
  /* Base palette */
  --bg: #0b0d10;
  --bg-inset: #0f1520;
  --panel: #14202b;
  --panel-2: #1a2535;
  --border: #2a3447;
  --text: #e8edf4;
  --muted: #6b7a8d;
  --accent: #4ea1ff;

  /* Semantic */
  --good: #6dd39a;
  --bad: #ff6b6b;
  --warn: #ffd86b;

  /* Rarity */
  --r-common: #9ca7b3;
  --r-uncommon: #6dd39a;
  --r-rare: #59a0ff;
  --r-epic: #c97aff;
  --r-legendary: #ffd86b;
  --r-myth: #ff9ecd;

  /* Faction */
  --faction-resistance: #6dd39a;
  --faction-corp-greed: #c97aff;
  --faction-exile: #ffd86b;
  --faction-neutral: #9ca7b3;

  /* Role */
  --role-atk: #ff7a59;
  --role-def: #59a0ff;
  --role-sup: #6dd39a;

  /* Spacing */
  --radius: 6px;
  --radius-sm: 4px;
  --radius-lg: 10px;
}
```

- [ ] **Step 2: Create global.css**

```css
/* frontend/src/styles/global.css */
@import './tokens.css';

*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.5;
}

button {
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--text);
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  transition: border-color 0.15s, background 0.15s;
}
button:hover { border-color: var(--accent); }
button.primary { background: var(--accent); color: #0b0d10; border-color: var(--accent); font-weight: 700; }
button.primary:hover { background: #6db5ff; }
button.secondary { background: var(--panel-2); }
button:disabled { opacity: 0.4; cursor: not-allowed; }

input, textarea, select {
  background: var(--bg-inset);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
}
input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: var(--accent);
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.muted { color: var(--muted); }
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}
.stack { display: flex; flex-direction: column; gap: 12px; }
.row { display: flex; align-items: center; gap: 8px; }
.pill {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 600;
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--border);
}
.pill.bad { background: rgba(255,107,107,0.15); border-color: var(--bad); color: var(--bad); }
.pill.good { background: rgba(109,211,154,0.15); border-color: var(--good); color: var(--good); }

/* Skeleton shimmer */
.skeleton {
  background: linear-gradient(90deg, var(--panel-2) 0%, var(--panel) 50%, var(--panel-2) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  border-radius: var(--radius-sm);
  color: transparent !important;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; background: var(--panel-2); }
}

/* Empty state */
.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 32px 20px; text-align: center;
  border: 1px dashed var(--border); border-radius: var(--radius);
  background: rgba(255,255,255,0.02); color: var(--muted);
}
.empty-state-icon { font-size: 36px; opacity: 0.6; }
.empty-state-msg { font-size: 14px; font-weight: 600; color: var(--text); }
.empty-state-hint { font-size: 12px; max-width: 360px; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles/
git commit -m "feat: add design token CSS and global styles"
```

---

### Task 3: TypeScript types

**Files:**
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/test/types.test.ts
import type { Me, Hero, HeroTemplate, Stage, Guild, Notification } from '../types'

// TypeScript compile test — if the interfaces are missing or wrong, tsc fails.
const me: Me = {
  id: 1, email: 'a@b.com', coins: 0, gems: 0, shards: 0,
  access_cards: 0, free_summon_credits: 0, energy: 60, energy_cap: 60,
  pulls_since_epic: 0, stages_cleared: [], arena_rating: 1000,
  arena_wins: 0, arena_losses: 0, account_level: 1, account_xp: 0,
  qol_unlocks: {}, active_cosmetic_frame: '',
}

const tmpl: HeroTemplate = {
  id: 1, code: 'hr_001', name: 'Test', rarity: 'COMMON', role: 'ATK',
  faction: 'EXILE', attack_kind: 'melee', base_hp: 100, base_atk: 10,
  base_def: 10, base_spd: 10,
}

const hero: Hero = {
  id: 1, template: tmpl, level: 1, stars: 1, special_level: 1,
  power: 100, hp: 100, atk: 10, def_: 10, spd: 10,
  has_variance: false, variance_net: 0, dupe_count: 1, instance_ids: [1],
}

describe('types compile', () => {
  it('Me shape', () => expect(me.email).toBe('a@b.com'))
  it('Hero shape', () => expect(hero.template.name).toBe('Test'))
})
```

- [ ] **Step 2: Run — expect FAIL (types not defined yet)**

```bash
cd frontend && npx vitest run src/test/types.test.ts
```
Expected: TypeScript error — `Cannot find module '../types'`

- [ ] **Step 3: Create types/index.ts**

```typescript
// frontend/src/types/index.ts

export interface Me {
  id: number
  email: string
  coins: number
  gems: number
  shards: number
  access_cards: number
  free_summon_credits: number
  energy: number
  energy_cap: number
  pulls_since_epic: number
  stages_cleared: string[]
  arena_rating: number
  arena_wins: number
  arena_losses: number
  account_level: number
  account_xp: number
  qol_unlocks: Record<string, unknown>
  active_cosmetic_frame: string
}

export interface HeroTemplate {
  id: number
  code: string
  name: string
  rarity: 'COMMON' | 'UNCOMMON' | 'RARE' | 'EPIC' | 'LEGENDARY' | 'MYTH'
  role: 'ATK' | 'DEF' | 'SUP'
  faction: 'RESISTANCE' | 'CORP_GREED' | 'EXILE' | 'NEUTRAL'
  attack_kind: 'melee' | 'ranged'
  base_hp: number
  base_atk: number
  base_def: number
  base_spd: number
}

export interface Hero {
  id: number
  template: HeroTemplate
  level: number
  stars: number
  special_level: number
  power: number
  hp: number
  atk: number
  def_: number
  spd: number
  has_variance: boolean
  variance_net: number
  dupe_count: number
  instance_ids: number[]
  has_bust?: boolean
  has_card?: boolean
}

export interface Stage {
  id: number
  code: string
  name: string
  order: number
  energy_cost: number
  recommended_power: number
  coin_reward: number
  first_clear_gems: number
  first_clear_shards: number
  cleared: boolean
  difficulty_tier: 'NORMAL' | 'HARD' | 'NIGHTMARE'
  requires_code: string | null
  locked: boolean
}

export interface Guild {
  id: number
  name: string
  tag: string
  description: string
  member_count: number
  members?: GuildMember[]
}

export interface GuildMember {
  account_id: number
  name: string
  role: 'LEADER' | 'OFFICER' | 'MEMBER'
  arena_rating: number
}

export interface Notification {
  id: number
  title: string
  body: string | null
  icon: string | null
  link: string | null
  read_at: string | null
  created_at: string
}

export interface ShopProduct {
  sku: string
  title: string
  description: string
  kind: string
  price_cents: number
  currency_code: string
  contents: Record<string, unknown>
  has_stripe: boolean
}

export interface BattleLog {
  id: number
  stage_code: string
  outcome: 'WIN' | 'LOSS'
  created_at: string
  log: BattleEvent[]
}

export interface BattleEvent {
  type: string
  actor?: string
  target?: string
  amount?: number
  crit?: boolean
  channel?: 'melee' | 'ranged'
  source?: string
  [key: string]: unknown
}

export interface UnitSnapshot {
  uid: string
  name: string
  side: 'A' | 'B'
  role: string
  hp: number
  max_hp: number
  dead: boolean
  shielded: boolean
  limit_gauge: number
  limit_gauge_max: number
}

export interface InteractiveState {
  session_id: string
  status: 'WAITING' | 'DONE'
  pending: {
    actor_uid: string
    actor_name: string
    turn_number: number
    enemies: UnitSnapshot[]
  } | null
  log_delta: BattleEvent[]
  team_a: UnitSnapshot[]
  team_b: UnitSnapshot[]
  outcome: string | null
  rewards: Record<string, unknown> | null
  participants: unknown[]
}

export interface Raid {
  id: number
  boss_name: string
  remaining_hp: number
  max_hp: number
  status: string
  guild_id: number
}
```

- [ ] **Step 4: Run — expect PASS**

```bash
npx vitest run src/test/types.test.ts
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ frontend/src/test/types.test.ts
git commit -m "feat: add TypeScript types for all API resources"
```

---

### Task 4: Zustand auth + UI stores

**Files:**
- Create: `frontend/src/store/auth.ts`
- Create: `frontend/src/store/ui.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/test/auth.test.ts`

- [ ] **Step 1: Create test setup file**

```typescript
// frontend/src/test/setup.ts
import '@testing-library/jest-dom'
```

- [ ] **Step 2: Write failing test**

```typescript
// frontend/src/test/auth.test.ts
import { useAuthStore } from '../store/auth'
import { act } from '@testing-library/react'

beforeEach(() => {
  localStorage.clear()
  useAuthStore.setState({ jwt: null })
})

describe('useAuthStore', () => {
  it('starts null', () => {
    expect(useAuthStore.getState().jwt).toBeNull()
  })

  it('setJwt stores in state and localStorage', () => {
    act(() => useAuthStore.getState().setJwt('tok123'))
    expect(useAuthStore.getState().jwt).toBe('tok123')
    expect(localStorage.getItem('heroproto_jwt')).toBe('tok123')
  })

  it('clearJwt removes from state and localStorage', () => {
    act(() => useAuthStore.getState().setJwt('tok123'))
    act(() => useAuthStore.getState().clearJwt())
    expect(useAuthStore.getState().jwt).toBeNull()
    expect(localStorage.getItem('heroproto_jwt')).toBeNull()
  })

  it('rehydrates from localStorage on import', () => {
    localStorage.setItem('heroproto_jwt', 'existing')
    // Re-import to trigger rehydration (Zustand persist middleware)
    const { useAuthStore: fresh } = require('../store/auth')
    // persist middleware rehydrates synchronously on create
    expect(fresh.getState().jwt).toBe('existing')
  })
})
```

- [ ] **Step 3: Run — expect FAIL**

```bash
npx vitest run src/test/auth.test.ts
```
Expected: FAIL — `Cannot find module '../store/auth'`

- [ ] **Step 4: Create auth store**

```typescript
// frontend/src/store/auth.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  jwt: string | null
  setJwt: (token: string) => void
  clearJwt: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      jwt: null,
      setJwt: (token) => set({ jwt: token }),
      clearJwt: () => set({ jwt: null }),
    }),
    {
      name: 'heroproto_jwt',
      partialize: (state) => ({ jwt: state.jwt }),
    }
  )
)
```

- [ ] **Step 5: Create UI store (toasts)**

```typescript
// frontend/src/store/ui.ts
import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: string
  message: string
  kind: ToastKind
}

interface UiState {
  toasts: Toast[]
  addToast: (message: string, kind: ToastKind) => void
  dismissToast: (id: string) => void
}

export const useUiStore = create<UiState>((set) => ({
  toasts: [],
  addToast: (message, kind) => {
    const id = Math.random().toString(36).slice(2)
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }))
    const ttl = kind === 'error' ? 5000 : 3500
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), ttl)
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

// Convenience helpers matching the old toast.js API
export const toast = {
  success: (msg: string) => useUiStore.getState().addToast(msg, 'success'),
  error: (msg: string) => useUiStore.getState().addToast(msg, 'error'),
  info: (msg: string) => useUiStore.getState().addToast(msg, 'info'),
}
```

- [ ] **Step 6: Run — expect PASS**

```bash
npx vitest run src/test/auth.test.ts
```
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/store/ frontend/src/test/
git commit -m "feat: add Zustand auth and UI stores with persistence"
```

---

### Task 5: API client + useMe hook

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/me.ts`
- Create: `frontend/src/hooks/useMe.ts`
- Create: `frontend/src/test/apiClient.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/test/apiClient.test.ts
import { apiFetch } from '../api/client'
import { useAuthStore } from '../store/auth'

beforeEach(() => {
  localStorage.clear()
  useAuthStore.setState({ jwt: null })
  vi.restoreAllMocks()
})

describe('apiFetch', () => {
  it('sends Authorization header when JWT present', async () => {
    useAuthStore.setState({ jwt: 'test-token' })
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    )
    vi.stubGlobal('fetch', mockFetch)

    await apiFetch('/me')

    expect(mockFetch).toHaveBeenCalledWith(
      '/me',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
  })

  it('omits Authorization header when no JWT', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    )
    vi.stubGlobal('fetch', mockFetch)

    await apiFetch('/me')

    const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>
    expect(headers['Authorization']).toBeUndefined()
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    ))
    await expect(apiFetch('/me')).rejects.toThrow('Not found')
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

```bash
npx vitest run src/test/apiClient.test.ts
```
Expected: FAIL — `Cannot find module '../api/client'`

- [ ] **Step 3: Create API client**

```typescript
// frontend/src/api/client.ts
import { useAuthStore } from '../store/auth'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const jwt = useAuthStore.getState().jwt
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> ?? {}),
  }
  if (jwt) headers['Authorization'] = `Bearer ${jwt}`

  const res = await fetch(url, { ...options, headers })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body.detail ?? body.message ?? message
    } catch {}
    // Detect "not enough X" for shop CTA (mirrors old toast.js logic)
    if (typeof message === 'string' && /not enough/i.test(message)) {
      // Let caller handle; they can check error.message
    }
    throw new ApiError(res.status, message)
  }

  return res.json() as Promise<T>
}

export async function apiPost<T = unknown>(url: string, body: unknown): Promise<T> {
  return apiFetch<T>(url, { method: 'POST', body: JSON.stringify(body) })
}

export async function apiDelete<T = unknown>(url: string): Promise<T> {
  return apiFetch<T>(url, { method: 'DELETE' })
}
```

- [ ] **Step 4: Create me API + useMe hook**

```typescript
// frontend/src/api/me.ts
import type { Me } from '../types'
import { apiFetch } from './client'

export const fetchMe = (): Promise<Me> => apiFetch<Me>('/me')
```

```typescript
// frontend/src/hooks/useMe.ts
import { useQuery } from '@tanstack/react-query'
import { fetchMe } from '../api/me'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  })
}
```

- [ ] **Step 5: Run — expect PASS**

```bash
npx vitest run src/test/apiClient.test.ts
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/ frontend/src/hooks/ frontend/src/test/apiClient.test.ts
git commit -m "feat: add typed API client and useMe query hook"
```

---

### Task 6: Zustand sound store

**Files:**
- Create: `frontend/src/store/sound.ts`

- [ ] **Step 1: Create sound store**

```typescript
// frontend/src/store/sound.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SoundState {
  muted: boolean
  master: number  // 0-1
  sfx: number     // 0-1
  setMute: (v: boolean) => void
  setMaster: (v: number) => void
  setSfx: (v: number) => void
  play: (cue: 'click' | 'tab' | 'ui' | 'combat' | 'gacha' | 'events') => void
}

export const useSoundStore = create<SoundState>()(
  persist(
    (set, get) => ({
      muted: false,
      master: 0.6,
      sfx: 0.8,
      setMute: (v) => set({ muted: v }),
      setMaster: (v) => set({ master: Math.max(0, Math.min(1, v)) }),
      setSfx: (v) => set({ sfx: Math.max(0, Math.min(1, v)) }),
      play: (_cue) => {
        // Stub — real audio implementation can wire in later.
        // Keeping the same interface as the old window.sound.play().
        if (get().muted) return
      },
    }),
    { name: 'heroproto_sound', partialize: (s) => ({ muted: s.muted, master: s.master, sfx: s.sfx }) }
  )
)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/store/sound.ts
git commit -m "feat: add Zustand sound store"
```

---

### Task 7: App shell + routing skeleton

**Files:**
- Create: `frontend/src/components/Layout/Shell.tsx`
- Create: `frontend/src/components/Layout/NavBar.tsx`
- Create: `frontend/src/components/Layout/CurrencyBar.tsx`
- Create: `frontend/src/components/Layout/BellPopover.tsx`
- Create: `frontend/src/components/Layout/SoundPopover.tsx`
- Create: `frontend/src/components/EmptyState.tsx`
- Create: `frontend/src/components/SkeletonGrid.tsx`
- Create: `frontend/src/routes/Stub.tsx`
- Create: `frontend/src/routes/Login.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/test/shell.test.tsx`

- [ ] **Step 1: Write failing shell test**

```typescript
// frontend/src/test/shell.test.tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shell } from '../components/Layout/Shell'
import { useAuthStore } from '../store/auth'

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>
      {children}
    </MemoryRouter>
  </QueryClientProvider>
)

beforeEach(() => useAuthStore.setState({ jwt: null }))

describe('Shell', () => {
  it('renders nav tabs', () => {
    render(<Shell />, { wrapper })
    expect(screen.getByText('Roster')).toBeInTheDocument()
    expect(screen.getByText('Stages')).toBeInTheDocument()
    expect(screen.getByText('Shop')).toBeInTheDocument()
  })

  it('hides currency bar when not logged in', () => {
    render(<Shell />, { wrapper })
    expect(screen.queryByTestId('currency-bar')).not.toBeInTheDocument()
  })

  it('shows currency bar when logged in', () => {
    useAuthStore.setState({ jwt: 'tok' })
    render(<Shell />, { wrapper })
    expect(screen.getByTestId('currency-bar')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

```bash
npx vitest run src/test/shell.test.tsx
```
Expected: FAIL — `Cannot find module '../components/Layout/Shell'`

- [ ] **Step 3: Create EmptyState + SkeletonGrid**

```tsx
// frontend/src/components/EmptyState.tsx
interface Props { icon?: string; message: string; hint?: string }
export function EmptyState({ icon = '📭', message, hint }: Props) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <div className="empty-state-msg">{message}</div>
      {hint && <div className="empty-state-hint">{hint}</div>}
    </div>
  )
}
```

```tsx
// frontend/src/components/SkeletonGrid.tsx
interface Props { count?: number; height?: number }
export function SkeletonGrid({ count = 6, height = 90 }: Props) {
  return (
    <div className="skeleton-grid">
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} className="skeleton skeleton-box" style={{ height }} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Create CurrencyBar**

```tsx
// frontend/src/components/Layout/CurrencyBar.tsx
import { useMe } from '../../hooks/useMe'
import { useAuthStore } from '../../store/auth'

export function CurrencyBar() {
  const jwt = useAuthStore((s) => s.jwt)
  const { data: me } = useMe()

  if (!jwt || !me) return null

  return (
    <div data-testid="currency-bar" style={{
      display: 'flex', gap: 6, padding: '6px 16px',
      borderBottom: '1px solid var(--border)',
      background: 'var(--panel)', fontSize: 12, flexWrap: 'wrap', alignItems: 'center',
    }}>
      <span className="muted" style={{ marginRight: 4 }}>Wallet</span>
      <span className="cb-pill">💎 {me.gems}</span>
      <span className="cb-pill">✦ {me.shards}</span>
      <span className="cb-pill">🪙 {me.coins}</span>
      <span className="cb-pill">🎫 {me.access_cards}</span>
      <span className="cb-pill">⚡ {me.energy}/{me.energy_cap}</span>
      <span className="cb-pill">🎟️ {me.free_summon_credits}</span>
      <span className="cb-pill" style={{ marginLeft: 'auto' }}>Lv {me.account_level}</span>
    </div>
  )
}
```

- [ ] **Step 5: Create BellPopover stub**

```tsx
// frontend/src/components/Layout/BellPopover.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import type { Notification } from '../../types'

export function BellButton() {
  const [open, setOpen] = useState(false)
  const jwt = useAuthStore((s) => s.jwt)

  const { data: countData } = useQuery({
    queryKey: ['notifications', 'count'],
    queryFn: () => apiFetch<{ unread: number }>('/notifications/unread-count'),
    refetchInterval: 30_000,
    enabled: !!jwt,
  })
  const { data: listData } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => apiFetch<{ items: Notification[] }>('/notifications?limit=30'),
    enabled: open && !!jwt,
  })

  const unread = countData?.unread ?? 0

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen((v) => !v)}
        style={{ position: 'relative', background: 'transparent', border: '1px solid var(--border)', color: 'var(--muted)', padding: '4px 8px', borderRadius: 4, fontSize: 14 }}>
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -4, right: -4,
            background: 'var(--bad)', color: 'white',
            fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 8, minWidth: 14, textAlign: 'center',
          }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 40, right: 0, zIndex: 100,
          background: 'var(--panel)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 12, minWidth: 320, maxWidth: 400,
          maxHeight: 480, overflowY: 'auto', boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          <h3 style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase' }}>Notifications</h3>
          {!listData?.items?.length
            ? <p style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>No notifications yet.</p>
            : listData.items.map((n) => (
              <div key={n.id} style={{
                padding: '8px 10px', borderRadius: 4, marginBottom: 4,
                background: n.read_at ? 'transparent' : 'rgba(78,161,255,0.08)',
                borderLeft: `2px solid ${n.read_at ? 'var(--border)' : 'var(--accent)'}`,
              }}>
                <div style={{ fontWeight: 600, fontSize: 12 }}>{n.icon ?? '🔔'} {n.title}</div>
                {n.body && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{n.body}</div>}
              </div>
            ))
          }
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Create SoundPopover**

```tsx
// frontend/src/components/Layout/SoundPopover.tsx
import { useState } from 'react'
import { useSoundStore } from '../../store/sound'

export function SoundButton() {
  const [open, setOpen] = useState(false)
  const { muted, master, sfx, setMute, setMaster, setSfx } = useSoundStore()

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen((v) => !v)}
        style={{ background: 'transparent', border: '1px solid var(--border)', color: muted ? 'var(--bad)' : 'var(--muted)', padding: '4px 8px', borderRadius: 4, fontSize: 14 }}>
        {muted ? '🔇' : '🔊'}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 40, right: 0, zIndex: 100,
          background: 'var(--panel)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 14, minWidth: 240, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          <h3 style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase' }}>Sound</h3>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 8 }}>
            <span>Mute</span>
            <input type="checkbox" checked={muted} onChange={(e) => setMute(e.target.checked)} style={{ width: 18, height: 18 }} />
          </label>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 8 }}>
            <span>Master {Math.round(master * 100)}%</span>
            <input type="range" min={0} max={100} value={Math.round(master * 100)}
              onChange={(e) => setMaster(Number(e.target.value) / 100)} style={{ flex: 1 }} />
          </label>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span>SFX {Math.round(sfx * 100)}%</span>
            <input type="range" min={0} max={100} value={Math.round(sfx * 100)}
              onChange={(e) => setSfx(Number(e.target.value) / 100)} style={{ flex: 1 }} />
          </label>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Create NavBar**

```tsx
// frontend/src/components/Layout/NavBar.tsx
import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { BellButton } from './BellPopover'
import { SoundButton } from './SoundPopover'
import { useMe } from '../../hooks/useMe'

const NAV_TABS = [
  { path: '/app/login', label: 'Login', authRequired: false },
  { path: '/app/me', label: 'Me', authRequired: true },
  { path: '/app/roster', label: 'Roster', authRequired: true },
  { path: '/app/summon', label: 'Summon', authRequired: true },
  { path: '/app/crafting', label: '⚒️ Crafting', authRequired: true },
  { path: '/app/stages', label: 'Stages', authRequired: true },
  { path: '/app/daily', label: 'Daily', authRequired: true },
  { path: '/app/story', label: '📖 Story', authRequired: true },
  { path: '/app/friends', label: '🤝 Friends', authRequired: true },
  { path: '/app/achievements', label: '🏆 Achievements', authRequired: true },
  { path: '/app/arena', label: 'Arena', authRequired: true },
  { path: '/app/guild', label: 'Guild', authRequired: true },
  { path: '/app/raids', label: '🐉 Raid', authRequired: true },
  { path: '/app/shop', label: 'Shop', authRequired: true },
  { path: '/app/account', label: '⚙️ Account', authRequired: true },
]

export function NavBar() {
  const jwt = useAuthStore((s) => s.jwt)
  const { data: me } = useMe()

  const { data: eventData } = useQuery({
    queryKey: ['active-event'],
    queryFn: () => apiFetch<unknown>('/events/active'),
    refetchInterval: 60_000,
    enabled: !!jwt,
    retry: false,
  })
  const hasEvent = !!eventData

  const visibleTabs = NAV_TABS.filter((t) => !t.authRequired || !!jwt)

  const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
    background: 'transparent',
    color: isActive ? 'var(--text)' : 'var(--muted)',
    padding: '6px 12px',
    borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
    borderRadius: 0,
    fontSize: 13,
    textDecoration: 'none',
    display: 'inline-block',
    cursor: 'pointer',
    border: 'none',
    borderBottomWidth: 2,
    borderBottomStyle: 'solid' as const,
    borderBottomColor: isActive ? 'var(--accent)' : 'transparent',
  })

  return (
    <header style={{
      background: 'var(--panel)', padding: '10px 18px',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', gap: 20,
      position: 'sticky', top: 0, zIndex: 50,
    }}>
      <h1 style={{ fontSize: 16, margin: 0, color: 'var(--text)' }}>hero-proto</h1>
      <nav style={{ display: 'flex', gap: 2, overflowX: 'auto' }}>
        {visibleTabs.map((t) => (
          <NavLink key={t.path} to={t.path} style={navLinkStyle}>{t.label}</NavLink>
        ))}
        {hasEvent && jwt && (
          <NavLink to="/app/event" style={navLinkStyle}>⚡ Event</NavLink>
        )}
      </nav>
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        {me && (
          <span style={{
            color: 'var(--good)', fontSize: 12, padding: '4px 10px',
            background: 'var(--bg-inset)', borderRadius: 4,
            border: '1px solid color-mix(in srgb, var(--good) 40%, transparent)',
          }}>
            ✓ {me.email.split('@')[0]}
          </span>
        )}
        {jwt && <BellButton />}
        <SoundButton />
      </div>
    </header>
  )
}
```

- [ ] **Step 8: Create Shell**

```tsx
// frontend/src/components/Layout/Shell.tsx
import { Outlet } from 'react-router-dom'
import { NavBar } from './NavBar'
import { CurrencyBar } from './CurrencyBar'
import { ToastContainer } from '../Toast'

export function Shell() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <NavBar />
      <CurrencyBar />
      <main style={{ padding: 18, maxWidth: 1100, margin: '0 auto', width: '100%', flex: 1 }}>
        <Outlet />
      </main>
      <ToastContainer />
    </div>
  )
}
```

- [ ] **Step 9: Create Toast component**

```tsx
// frontend/src/components/Toast.tsx
import { useUiStore } from '../store/ui'

export function ToastContainer() {
  const toasts = useUiStore((s) => s.toasts)
  const dismiss = useUiStore((s) => s.dismissToast)

  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed', bottom: 20, left: '50%', transform: 'translateX(-50%)',
      zIndex: 9000, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center',
    }}>
      {toasts.map((t) => (
        <div key={t.id} onClick={() => dismiss(t.id)} style={{
          padding: '10px 18px', borderRadius: 6, cursor: 'pointer',
          fontSize: 13, fontWeight: 500, maxWidth: 420, textAlign: 'center',
          background: t.kind === 'error' ? 'var(--bad)' : t.kind === 'success' ? 'var(--good)' : 'var(--accent)',
          color: '#0b0d10', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {t.message}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 10: Create route stubs**

```tsx
// frontend/src/routes/Stub.tsx
interface Props { name: string }
export function Stub({ name }: Props) {
  return (
    <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>🚧</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>{name}</div>
      <div style={{ fontSize: 12, marginTop: 6 }}>Coming in the next plan phase.</div>
    </div>
  )
}
```

```tsx
// frontend/src/routes/Login.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { apiFetch } from '../api/client'
import { toast } from '../store/ui'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const setJwt = useAuthStore((s) => s.setJwt)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await apiFetch<{ access_token: string }>('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
      })
      setJwt(data.access_token)
      navigate('/app/me')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: '60px auto' }}>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Sign in</h2>
        <form onSubmit={handleSubmit} className="stack">
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              required style={{ width: '100%' }} placeholder="you@example.com" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              required style={{ width: '100%' }} />
          </div>
          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 11: Create App.tsx with all routes**

```tsx
// frontend/src/App.tsx
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shell } from './components/Layout/Shell'
import { Login } from './routes/Login'
import { Stub } from './routes/Stub'
import '../src/styles/global.css'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/app/me" replace /> },
  {
    path: '/app',
    element: <Shell />,
    children: [
      { index: true, element: <Navigate to="/app/me" replace /> },
      { path: 'login', element: <Login /> },
      { path: 'me', element: <Stub name="Me" /> },
      { path: 'roster', children: [
        { index: true, element: <Stub name="Roster" /> },
        { path: ':heroId', element: <Stub name="Hero Detail" /> },
      ]},
      { path: 'summon', element: <Stub name="Summon" /> },
      { path: 'crafting', element: <Stub name="Crafting" /> },
      { path: 'stages', element: <Stub name="Stages" /> },
      { path: 'daily', element: <Stub name="Daily" /> },
      { path: 'story', element: <Stub name="Story" /> },
      { path: 'friends', children: [
        { index: true, element: <Stub name="Friends" /> },
        { path: 'messages', element: <Stub name="Messages" /> },
      ]},
      { path: 'achievements', element: <Stub name="Achievements" /> },
      { path: 'arena', element: <Stub name="Arena" /> },
      { path: 'guild', children: [
        { index: true, element: <Stub name="Guild" /> },
        { path: 'members', element: <Stub name="Guild Members" /> },
        { path: 'chat', element: <Stub name="Guild Chat" /> },
        { path: 'raids', element: <Stub name="Guild Raids" /> },
      ]},
      { path: 'raids', element: <Stub name="Raids" /> },
      { path: 'shop', element: <Stub name="Shop" /> },
      { path: 'account', element: <Stub name="Account" /> },
      { path: 'event', element: <Stub name="Event" /> },
    ],
  },
  {
    path: '/battle',
    children: [
      { path: 'setup', element: <Stub name="Battle Setup" /> },
      { path: ':id/watch', element: <Stub name="Battle Watch" /> },
      { path: ':id/play', element: <Stub name="Battle Play" /> },
      { path: ':id/replay', element: <Stub name="Battle Replay" /> },
    ],
  },
])

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
```

- [ ] **Step 12: Update main.tsx**

```tsx
// frontend/src/main.tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles/global.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

- [ ] **Step 13: Run shell tests — expect PASS**

```bash
npx vitest run src/test/shell.test.tsx
```
Expected: 3 passed.

- [ ] **Step 14: Verify dev server renders the app**

```bash
npm run dev
```
Open http://localhost:5173 — expect to see the nav bar and "Me 🚧 Coming in the next plan phase." stub at `/app/me`. Navigate to Roster, Stages, etc. — all should show stubs.

- [ ] **Step 15: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Shell layout, NavBar, CurrencyBar, Toast, Login route, all route stubs"
```

---

### Task 8: Run full test suite + verify build

**Files:** none created

- [ ] **Step 1: Run all frontend tests**

```bash
cd frontend && npx vitest run
```
Expected: all tests pass (types.test.ts, auth.test.ts, apiClient.test.ts, shell.test.tsx).

- [ ] **Step 2: Verify TypeScript compiles clean**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Verify production build works**

```bash
npm run build
```
Expected: `app/static/spa/` directory created with `index.html` and `assets/`.

- [ ] **Step 4: Verify Python test suite still passes**

```bash
cd .. && pytest -q
```
Expected: 634 passed, 3 skipped (backend untouched).

- [ ] **Step 5: Final commit**

```bash
git add app/static/spa/
git commit -m "chore: verify SPA scaffold — all tests green, build output confirmed"
```

---

**Plan 1 complete.** Next: `2026-04-27-spa-p2-core-tabs.md` — Me, Roster, Stages, Summon, Shop.
