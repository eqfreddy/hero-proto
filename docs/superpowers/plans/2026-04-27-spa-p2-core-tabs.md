# SPA Rewrite — Plan 2: Core Tabs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the five tabs players use every session — Me, Roster (+ Hero Detail), Stages, Summon, and Shop — each hitting the existing JSON API and reaching full feature parity with the HTMX partials.

**Architecture:** Each tab is a route component in `frontend/src/routes/`. Data fetched via TanStack Query hooks in `frontend/src/hooks/`. Shared presentational components (HeroCard, StatBar, RarityPill) in `frontend/src/components/`. Mutations (buy, equip, summon) call `apiPost()` then invalidate the relevant query key.

**Tech Stack:** React 18 + TypeScript, TanStack Query v5, Zustand, React Router v6, Vitest + RTL

**Prerequisite:** Plan 1 complete — `npm run dev` serves the shell with stubs.

---

## File map

**Create:**
- `frontend/src/api/heroes.ts`
- `frontend/src/api/stages.ts`
- `frontend/src/api/summon.ts`
- `frontend/src/api/shop.ts`
- `frontend/src/hooks/useHeroes.ts`
- `frontend/src/hooks/useStages.ts`
- `frontend/src/components/HeroCard.tsx`
- `frontend/src/components/StatBar.tsx`
- `frontend/src/components/RarityPill.tsx`
- `frontend/src/routes/Me.tsx`
- `frontend/src/routes/Roster/index.tsx`
- `frontend/src/routes/Roster/HeroDetail.tsx`
- `frontend/src/routes/Stages.tsx`
- `frontend/src/routes/Summon.tsx`
- `frontend/src/routes/Shop.tsx`
- `frontend/src/test/heroCard.test.tsx`
- `frontend/src/test/me.test.tsx`

**Modify:**
- `frontend/src/App.tsx` — replace Stub for me/roster/stages/summon/shop with real imports

---

### Task 1: Hero API + hooks + HeroCard component

**Files:**
- Create: `frontend/src/api/heroes.ts`
- Create: `frontend/src/hooks/useHeroes.ts`
- Create: `frontend/src/components/HeroCard.tsx`
- Create: `frontend/src/components/RarityPill.tsx`
- Create: `frontend/src/test/heroCard.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/test/heroCard.test.tsx
import { render, screen } from '@testing-library/react'
import { HeroCard } from '../components/HeroCard'
import type { Hero } from '../types'

const hero: Hero = {
  id: 1,
  template: {
    id: 1, code: 'hr_jaded_intern', name: 'Jaded Intern',
    rarity: 'COMMON', role: 'ATK', faction: 'EXILE',
    attack_kind: 'melee', base_hp: 100, base_atk: 10, base_def: 10, base_spd: 10,
  },
  level: 5, stars: 2, special_level: 1,
  power: 450, hp: 200, atk: 30, def_: 20, spd: 15,
  has_variance: false, variance_net: 0, dupe_count: 1, instance_ids: [1],
}

describe('HeroCard', () => {
  it('shows hero name', () => {
    render(<HeroCard hero={hero} />)
    expect(screen.getByText('Jaded Intern')).toBeInTheDocument()
  })

  it('shows power', () => {
    render(<HeroCard hero={hero} />)
    expect(screen.getByText(/450/)).toBeInTheDocument()
  })

  it('shows rarity pill', () => {
    render(<HeroCard hero={hero} />)
    expect(screen.getByText('COMMON')).toBeInTheDocument()
  })

  it('shows dupe badge when count > 1', () => {
    render(<HeroCard hero={{ ...hero, dupe_count: 3 }} />)
    expect(screen.getByText('×3')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd frontend && npx vitest run src/test/heroCard.test.tsx
```
Expected: FAIL — `Cannot find module '../components/HeroCard'`

- [ ] **Step 3: Create RarityPill**

```tsx
// frontend/src/components/RarityPill.tsx
import type { HeroTemplate } from '../types'

const RARITY_COLORS: Record<HeroTemplate['rarity'], string> = {
  COMMON: 'var(--r-common)',
  UNCOMMON: 'var(--r-uncommon)',
  RARE: 'var(--r-rare)',
  EPIC: 'var(--r-epic)',
  LEGENDARY: 'var(--r-legendary)',
  MYTH: 'var(--r-myth)',
}

interface Props { rarity: HeroTemplate['rarity']; size?: 'sm' | 'md' }
export function RarityPill({ rarity, size = 'sm' }: Props) {
  const color = RARITY_COLORS[rarity]
  return (
    <span style={{
      display: 'inline-block', padding: size === 'sm' ? '1px 6px' : '2px 8px',
      borderRadius: 10, fontSize: size === 'sm' ? 10 : 11, fontWeight: 700,
      background: `color-mix(in srgb, ${color} 20%, transparent)`,
      border: `1px solid ${color}`, color,
    }}>
      {rarity}
    </span>
  )
}
```

- [ ] **Step 4: Create HeroCard**

```tsx
// frontend/src/components/HeroCard.tsx
import type { Hero } from '../types'
import { RarityPill } from './RarityPill'

const ROLE_COLORS = { ATK: 'var(--role-atk)', DEF: 'var(--role-def)', SUP: 'var(--role-sup)' }

interface Props {
  hero: Hero
  onClick?: () => void
  selected?: boolean
}

export function HeroCard({ hero, onClick, selected }: Props) {
  const { template: t } = hero
  const portraitUrl = `/app/static/heroes/cards/${t.code}.png`
  const bustUrl = `/app/static/heroes/busts/${t.code}.png`
  const placeholderUrl = `/placeholder/hero/${t.code}.svg`

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--panel)',
        border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        transition: 'border-color 0.15s',
      }}
    >
      {/* Portrait */}
      <div style={{ position: 'relative', aspectRatio: '1', background: 'var(--bg-inset)', overflow: 'hidden' }}>
        <img
          src={hero.has_card ? portraitUrl : hero.has_bust ? bustUrl : placeholderUrl}
          alt={t.name}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onError={(e) => { (e.target as HTMLImageElement).src = placeholderUrl }}
        />
        {/* Role badge */}
        <span style={{
          position: 'absolute', top: 4, left: 4,
          background: ROLE_COLORS[t.role], color: '#0b0d10',
          fontSize: 9, fontWeight: 800, padding: '1px 5px', borderRadius: 3,
        }}>
          {t.role}
        </span>
        {/* Dupe badge */}
        {hero.dupe_count > 1 && (
          <span style={{
            position: 'absolute', top: 4, right: 4,
            background: 'rgba(0,0,0,0.75)', color: 'var(--warn)',
            fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          }}>
            ×{hero.dupe_count}
          </span>
        )}
        {/* Variance badge */}
        {hero.has_variance && (
          <span style={{
            position: 'absolute', bottom: 4, right: 4, fontSize: 9,
            color: hero.variance_net > 0 ? 'var(--good)' : 'var(--bad)',
            background: 'rgba(0,0,0,0.7)', padding: '1px 4px', borderRadius: 3,
          }}>
            {hero.variance_net > 0 ? '+' : ''}{(hero.variance_net * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {/* Info */}
      <div style={{ padding: '8px 10px' }}>
        <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {t.name}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <RarityPill rarity={t.rarity} />
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            ⚡ {hero.power}
          </span>
        </div>
        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3 }}>
          {'⭐'.repeat(hero.stars)} Lv {hero.level}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create heroes API + hook**

```typescript
// frontend/src/api/heroes.ts
import type { Hero } from '../types'
import { apiFetch, apiPost } from './client'

export const fetchHeroes = (): Promise<Hero[]> => apiFetch<Hero[]>('/heroes')
export const fetchHero = (id: number): Promise<Hero> => apiFetch<Hero>(`/heroes/${id}`)
export const ascendHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/ascend`, {})
export const skillUpHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/skill_up`, {})
```

```typescript
// frontend/src/hooks/useHeroes.ts
import { useQuery } from '@tanstack/react-query'
import { fetchHeroes, fetchHero } from '../api/heroes'

export function useHeroes() {
  return useQuery({ queryKey: ['heroes'], queryFn: fetchHeroes, staleTime: 5 * 60_000 })
}

export function useHero(id: number) {
  return useQuery({ queryKey: ['heroes', id], queryFn: () => fetchHero(id), staleTime: 5 * 60_000 })
}
```

- [ ] **Step 6: Run — expect PASS**

```bash
npx vitest run src/test/heroCard.test.tsx
```
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add HeroCard component, RarityPill, heroes API + useHeroes hook"
```

---

### Task 2: Me tab

**Files:**
- Create: `frontend/src/routes/Me.tsx`
- Create: `frontend/src/test/me.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/test/me.test.tsx
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { MeRoute } from '../routes/Me'

const mockMe = {
  id: 1, email: 'player@test.com', coins: 1000, gems: 50, shards: 20,
  access_cards: 5, free_summon_credits: 3, energy: 45, energy_cap: 60,
  pulls_since_epic: 12, stages_cleared: ['tutorial_first_ticket'],
  arena_rating: 1050, arena_wins: 5, arena_losses: 3,
  account_level: 4, account_xp: 350, qol_unlocks: {}, active_cosmetic_frame: '',
}

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: mockMe, isLoading: false }),
}))

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
)

describe('MeRoute', () => {
  it('shows account email', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getByText(/player@test\.com/)).toBeInTheDocument()
  })

  it('shows coins', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getByText(/1,000/)).toBeInTheDocument()
  })

  it('shows account level', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getByText(/Level 4/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — expect FAIL**

```bash
npx vitest run src/test/me.test.tsx
```
Expected: FAIL — `Cannot find module '../routes/Me'`

- [ ] **Step 3: Create Me.tsx**

```tsx
// frontend/src/routes/Me.tsx
import { useMe } from '../hooks/useMe'
import { useAuthStore } from '../store/auth'
import { useQueryClient } from '@tanstack/react-query'
import { apiPost, apiFetch } from '../api/client'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { useState } from 'react'

export function MeRoute() {
  const { data: me, isLoading } = useMe()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const [claimingBonus, setClaimingBonus] = useState(false)
  const [refilling, setRefilling] = useState(false)

  if (isLoading) return <SkeletonGrid count={4} height={80} />
  if (!me) return <div className="muted">Not signed in.</div>

  async function claimDailyBonus() {
    setClaimingBonus(true)
    try {
      const res = await apiPost<{ reward: Record<string, number> }>('/me/daily-bonus', {})
      const parts = Object.entries(res.reward).filter(([, v]) => v > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Daily bonus: ${parts.join(', ')}` : 'Claimed!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to claim bonus')
    } finally {
      setClaimingBonus(false)
    }
  }

  async function refillEnergy() {
    setRefilling(true)
    try {
      await apiPost('/me/refill-energy', { gems: 50 })
      toast.success('Energy refilled!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to refill')
    } finally {
      setRefilling(false)
    }
  }

  function logout() {
    clearJwt()
    qc.clear()
  }

  return (
    <div className="stack">
      {/* Account card */}
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Account</h2>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong>{me.email}</strong>
            <span className="muted"> · id {me.id}</span>
          </div>
          <button onClick={logout} style={{ fontSize: 12 }}>Sign out</button>
        </div>
      </div>

      {/* Level + XP */}
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Level {me.account_level}</h2>
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 8, overflow: 'hidden', marginTop: 4 }}>
          <div style={{
            height: '100%', borderRadius: 4, background: 'var(--accent)',
            width: `${Math.min(100, (me.account_xp / Math.max(1, me.account_xp + 100)) * 100)}%`,
          }} />
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{me.account_xp} XP</div>
      </div>

      {/* Currencies */}
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Currencies</h2>
        <div className="row" style={{ gap: 24, flexWrap: 'wrap' }}>
          {[
            ['💎', 'Gems', me.gems],
            ['✦', 'Shards', me.shards],
            ['🪙', 'Coins', me.coins.toLocaleString()],
            ['🎫', 'Access Cards', me.access_cards],
            ['🎟️', 'Free Summons', me.free_summon_credits],
          ].map(([icon, label, val]) => (
            <div key={String(label)}>
              <div className="muted" style={{ fontSize: 11 }}>{icon} {label}</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Energy */}
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Energy</h2>
            <div style={{ fontSize: 22, fontWeight: 700 }}>⚡ {me.energy} / {me.energy_cap}</div>
          </div>
          <button onClick={refillEnergy} disabled={refilling} className="secondary" style={{ fontSize: 12 }}>
            {refilling ? '…' : 'Refill (50 💎)'}
          </button>
        </div>
      </div>

      {/* Daily bonus */}
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Daily Bonus</h2>
            <div className="muted" style={{ fontSize: 12 }}>Streak login rewards</div>
          </div>
          <button onClick={claimDailyBonus} disabled={claimingBonus} className="primary">
            {claimingBonus ? '…' : 'Claim'}
          </button>
        </div>
      </div>

      {/* Arena */}
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Arena</h2>
        <div className="row" style={{ gap: 24 }}>
          <div><div className="muted" style={{ fontSize: 11 }}>Rating</div><div style={{ fontSize: 20, fontWeight: 700 }}>{me.arena_rating}</div></div>
          <div><div className="muted" style={{ fontSize: 11 }}>W / L</div><div style={{ fontSize: 20, fontWeight: 700 }}>{me.arena_wins} / {me.arena_losses}</div></div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Wire Me route in App.tsx**

In `frontend/src/App.tsx`, replace:
```tsx
{ path: 'me', element: <Stub name="Me" /> },
```
with:
```tsx
{ path: 'me', element: <MeRoute /> },
```
And add the import:
```tsx
import { MeRoute } from './routes/Me'
```

- [ ] **Step 5: Run — expect PASS**

```bash
npx vitest run src/test/me.test.tsx
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Me tab with account, currencies, energy, daily bonus, arena"
```

---

### Task 3: Roster tab + Hero Detail

**Files:**
- Create: `frontend/src/routes/Roster/index.tsx`
- Create: `frontend/src/routes/Roster/HeroDetail.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create Roster index**

```tsx
// frontend/src/routes/Roster/index.tsx
import { useHeroes } from '../../hooks/useHeroes'
import { HeroCard } from '../../components/HeroCard'
import { SkeletonGrid } from '../../components/SkeletonGrid'
import { EmptyState } from '../../components/EmptyState'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import type { HeroTemplate } from '../../types'

const RARITIES: HeroTemplate['rarity'][] = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']

export function RosterRoute() {
  const { data: heroes, isLoading } = useHeroes()
  const navigate = useNavigate()
  const [activeRarity, setActiveRarity] = useState<HeroTemplate['rarity'] | 'ALL'>('ALL')

  if (isLoading) return <SkeletonGrid />
  if (!heroes?.length) return (
    <EmptyState icon="⚔️" message="No heroes yet." hint="Head to Summon to pull your first hero." />
  )

  const filtered = activeRarity === 'ALL' ? heroes : heroes.filter((h) => h.template.rarity === activeRarity)

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Roster <span className="muted">({heroes.length})</span></h2>
      </div>

      {/* Rarity filter tabs */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {(['ALL', ...RARITIES] as const).map((r) => (
          <button
            key={r}
            onClick={() => setActiveRarity(r)}
            style={{
              fontSize: 11, padding: '3px 10px',
              background: activeRarity === r ? 'var(--accent)' : 'var(--panel)',
              color: activeRarity === r ? '#0b0d10' : 'var(--muted)',
              border: '1px solid var(--border)',
              borderRadius: 10, fontWeight: activeRarity === r ? 700 : 400,
            }}
          >
            {r}
          </button>
        ))}
      </div>

      {/* Hero grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12 }}>
        {filtered.map((hero) => (
          <HeroCard
            key={hero.id}
            hero={hero}
            onClick={() => navigate(`/app/roster/${hero.id}`)}
          />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create HeroDetail**

```tsx
// frontend/src/routes/Roster/HeroDetail.tsx
import { useParams, useNavigate } from 'react-router-dom'
import { useHero } from '../../hooks/useHeroes'
import { useQueryClient } from '@tanstack/react-query'
import { ascendHero, skillUpHero } from '../../api/heroes'
import { toast } from '../../store/ui'
import { RarityPill } from '../../components/RarityPill'
import { SkeletonGrid } from '../../components/SkeletonGrid'
import { useState } from 'react'

export function HeroDetailRoute() {
  const { heroId } = useParams<{ heroId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: hero, isLoading } = useHero(Number(heroId))
  const [loading, setLoading] = useState<'ascend' | 'skill' | null>(null)

  if (isLoading) return <SkeletonGrid count={3} height={100} />
  if (!hero) return <div className="muted">Hero not found.</div>

  const t = hero.template

  async function doAscend() {
    setLoading('ascend')
    try {
      await ascendHero(hero!.id)
      toast.success(`${t.name} ascended!`)
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(null) }
  }

  async function doSkillUp() {
    setLoading('skill')
    try {
      await skillUpHero(hero!.id)
      toast.success(`${t.name} skill upgraded!`)
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(null) }
  }

  return (
    <div className="stack" style={{ maxWidth: 480, margin: '0 auto' }}>
      <button onClick={() => navigate('/app/roster')} style={{ alignSelf: 'flex-start', fontSize: 12 }}>
        ← Back to Roster
      </button>
      <div className="card">
        <div className="row" style={{ gap: 16, alignItems: 'flex-start' }}>
          <img
            src={`/app/static/heroes/cards/${t.code}.png`}
            alt={t.name}
            style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 'var(--radius)', background: 'var(--bg-inset)' }}
            onError={(e) => { (e.target as HTMLImageElement).src = `/placeholder/hero/${t.code}.svg` }}
          />
          <div>
            <h2 style={{ margin: '0 0 4px' }}>{t.name}</h2>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              <RarityPill rarity={t.rarity} size="md" />
              <span className="pill">{t.role}</span>
              <span className="pill">{t.faction}</span>
            </div>
            <div style={{ marginTop: 6, color: 'var(--muted)', fontSize: 12 }}>
              {'⭐'.repeat(hero.stars)} Level {hero.level} · Special Lv {hero.special_level}
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 13 }}>Stats</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[['❤️ HP', hero.hp], ['⚔️ ATK', hero.atk], ['🛡️ DEF', hero.def_], ['💨 SPD', hero.spd], ['⚡ Power', hero.power]].map(([label, val]) => (
            <div key={String(label)}>
              <div className="muted" style={{ fontSize: 11 }}>{label}</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Upgrade actions */}
      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 13 }}>Upgrades</h3>
        <div className="row" style={{ gap: 8 }}>
          <button onClick={doAscend} disabled={!!loading} className="primary">
            {loading === 'ascend' ? '…' : '⭐ Star Up'}
          </button>
          <button onClick={doSkillUp} disabled={!!loading} className="secondary">
            {loading === 'skill' ? '…' : '🔮 Skill Up'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Wire routes in App.tsx**

Replace the roster children:
```tsx
{ path: 'roster', children: [
  { index: true, element: <Stub name="Roster" /> },
  { path: ':heroId', element: <Stub name="Hero Detail" /> },
]},
```
with:
```tsx
{ path: 'roster', children: [
  { index: true, element: <RosterRoute /> },
  { path: ':heroId', element: <HeroDetailRoute /> },
]},
```
Add imports:
```tsx
import { RosterRoute } from './routes/Roster'
import { HeroDetailRoute } from './routes/Roster/HeroDetail'
```

- [ ] **Step 4: Verify in browser**

```bash
cd frontend && npm run dev
```
Log in, navigate to Roster — hero grid should render with HeroCards. Click a card — detail sheet should open. Back button returns to grid.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Roster tab with rarity filter + Hero Detail route"
```

---

### Task 4: Stages tab

**Files:**
- Create: `frontend/src/api/stages.ts`
- Create: `frontend/src/hooks/useStages.ts`
- Create: `frontend/src/routes/Stages.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create stages API + hook**

```typescript
// frontend/src/api/stages.ts
import type { Stage } from '../types'
import { apiFetch } from './client'

export const fetchStages = (): Promise<Stage[]> => apiFetch<Stage[]>('/stages')
```

```typescript
// frontend/src/hooks/useStages.ts
import { useQuery } from '@tanstack/react-query'
import { fetchStages } from '../api/stages'
import { useHeroes } from './useHeroes'
import { useMemo } from 'react'

export function useStages() {
  return useQuery({ queryKey: ['stages'], queryFn: fetchStages, staleTime: 10 * 60_000 })
}

export function useTeamPower(): number {
  const { data: heroes } = useHeroes()
  return useMemo(() => {
    if (!heroes?.length) return 0
    const top3 = [...heroes].sort((a, b) => b.power - a.power).slice(0, 3)
    return top3.reduce((s, h) => s + h.power, 0)
  }, [heroes])
}
```

- [ ] **Step 2: Create Stages route**

```tsx
// frontend/src/routes/Stages.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStages, useTeamPower } from '../hooks/useStages'
import { useMe } from '../hooks/useMe'
import { apiPost } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import type { Stage } from '../types'

const TIER_LABELS = { NORMAL: 'Normal', HARD: 'Hard', NIGHTMARE: 'Nightmare' }

export function StagesRoute() {
  const { data: stages, isLoading } = useStages()
  const { data: me } = useMe()
  const teamPower = useTeamPower()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [activeTier, setActiveTier] = useState<Stage['difficulty_tier']>('NORMAL')
  const [battling, setBattling] = useState<number | null>(null)

  if (isLoading) return <SkeletonGrid />
  if (!stages?.length) return <EmptyState icon="🗺️" message="No stages available." />

  const byTier = stages.filter((s) => s.difficulty_tier === activeTier)

  async function startBattle(stage: Stage) {
    if (!me) return
    setBattling(stage.id)
    try {
      const res = await apiPost<{ id: number; outcome: string; log?: unknown[] }>('/battles', {
        stage_id: stage.id,
        hero_ids: [], // empty = server picks top 3
      })
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['stages'] })
      if (res.log) {
        navigate(`/battle/${res.id}/watch`)
      } else {
        toast.success(res.outcome === 'WIN' ? '⚔️ Victory!' : '💀 Defeated.')
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Battle failed')
    } finally {
      setBattling(null)
    }
  }

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Stages</h2>
        <span className="muted" style={{ fontSize: 12 }}>Team power: ⚡ {teamPower}</span>
      </div>

      {/* Tier tabs */}
      <div className="row" style={{ gap: 4 }}>
        {(['NORMAL', 'HARD', 'NIGHTMARE'] as const).map((tier) => (
          <button
            key={tier}
            onClick={() => setActiveTier(tier)}
            style={{
              fontSize: 12, padding: '4px 14px',
              background: activeTier === tier ? 'var(--accent)' : 'var(--panel)',
              color: activeTier === tier ? '#0b0d10' : 'var(--muted)',
              border: '1px solid var(--border)', borderRadius: 4,
              fontWeight: activeTier === tier ? 700 : 400,
            }}
          >
            {TIER_LABELS[tier]}
          </button>
        ))}
      </div>

      {/* Stage list */}
      <div className="stack" style={{ gap: 8 }}>
        {byTier.map((stage) => {
          const powerRatio = teamPower > 0 ? teamPower / stage.recommended_power : 0
          const powerColor = powerRatio >= 1.2 ? 'var(--good)' : powerRatio >= 0.8 ? 'var(--warn)' : 'var(--bad)'
          return (
            <div key={stage.id} className="card" style={{ padding: '12px 16px', opacity: stage.locked ? 0.5 : 1 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>
                    {stage.cleared ? '✅ ' : ''}{stage.name}
                  </div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                    ⚡ {stage.energy_cost} energy · Rec. {stage.recommended_power} power
                    <span style={{ color: powerColor }}> (yours: {teamPower})</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--warn)', marginTop: 2 }}>
                    🪙 {stage.coin_reward}
                    {stage.first_clear_gems > 0 && !stage.cleared && ` · 💎 ${stage.first_clear_gems} first clear`}
                  </div>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <button
                    className="primary"
                    disabled={stage.locked || battling === stage.id || (me?.energy ?? 0) < stage.energy_cost}
                    onClick={() => startBattle(stage)}
                    style={{ fontSize: 12 }}
                  >
                    {battling === stage.id ? '…' : stage.locked ? '🔒' : 'Battle'}
                  </button>
                  {stage.cleared && (
                    <button
                      onClick={() => {/* navigate to last replay */}}
                      style={{ fontSize: 11 }}
                    >
                      Replay
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Wire in App.tsx**

Replace `{ path: 'stages', element: <Stub name="Stages" /> }` with:
```tsx
{ path: 'stages', element: <StagesRoute /> },
```
Add import: `import { StagesRoute } from './routes/Stages'`

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Stages tab with tier filter, power comparison, battle button"
```

---

### Task 5: Summon tab

**Files:**
- Create: `frontend/src/api/summon.ts`
- Create: `frontend/src/routes/Summon.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create summon API**

```typescript
// frontend/src/api/summon.ts
import type { Hero } from '../types'
import { apiPost, apiFetch } from './client'

interface SummonResult { heroes: Hero[] }

export const pullStandard = (count: 1 | 10): Promise<SummonResult> =>
  apiPost('/summon/standard', { count })
export const pullEventBanner = (count: 1 | 10): Promise<SummonResult> =>
  apiPost('/summon/event-banner', { count })
export const fetchPityStatus = (): Promise<{ pulls_since_epic: number; pity_cap: number }> =>
  apiFetch('/summon/pity')
```

- [ ] **Step 2: Create Summon route**

```tsx
// frontend/src/routes/Summon.tsx
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { pullStandard } from '../api/summon'
import { toast } from '../store/ui'
import { HeroCard } from '../components/HeroCard'
import { SkeletonGrid } from '../components/SkeletonGrid'
import type { Hero } from '../types'

const PITY_CAP = 50

export function SummonRoute() {
  const { data: me, isLoading } = useMe()
  const { data: heroes } = useHeroes()
  const qc = useQueryClient()
  const [pulling, setPulling] = useState(false)
  const [lastPull, setLastPull] = useState<Hero[] | null>(null)

  if (isLoading) return <SkeletonGrid count={3} height={80} />

  const pityProgress = me?.pulls_since_epic ?? 0
  const pullsToEpic = Math.max(0, PITY_CAP - pityProgress)

  const recent = heroes ? [...heroes].sort((a, b) => b.id - a.id).slice(0, 10) : []

  async function pull(count: 1 | 10) {
    setPulling(true)
    setLastPull(null)
    try {
      const res = await pullStandard(count)
      setLastPull(res.heroes)
      const best = res.heroes.reduce((a, b) => {
        const order = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']
        return order.indexOf(b.template.rarity) > order.indexOf(a.template.rarity) ? b : a
      })
      toast.success(`Got ${res.heroes.length} hero${res.heroes.length > 1 ? 'es' : ''}! Best: ${best.template.rarity} ${best.template.name}`)
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Pull failed')
    } finally {
      setPulling(false)
    }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Summon</h2>

      {/* Pity bar */}
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Pity Progress</span>
          <span className="muted" style={{ fontSize: 12 }}>{pityProgress} / {PITY_CAP} — {pullsToEpic} to guaranteed EPIC</span>
        </div>
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 4,
            background: 'linear-gradient(90deg, var(--r-rare), var(--r-epic))',
            width: `${Math.min(100, (pityProgress / PITY_CAP) * 100)}%`,
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Pull buttons */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Standard Banner</h3>
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          Wallet: ✦ {me?.shards ?? 0} shards · 🎟️ {me?.free_summon_credits ?? 0} free
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="primary" onClick={() => pull(1)} disabled={pulling}>
            {pulling ? '…' : 'Pull ×1 (1 shard)'}
          </button>
          <button className="primary" onClick={() => pull(10)} disabled={pulling}>
            {pulling ? '…' : 'Pull ×10 (10 shards)'}
          </button>
        </div>
      </div>

      {/* Last pull result */}
      {lastPull && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Last Pull</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {lastPull.map((h) => <HeroCard key={h.id} hero={h} />)}
          </div>
        </div>
      )}

      {/* Recent pulls */}
      {recent.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent ({recent.length})</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {recent.map((h) => <HeroCard key={h.id} hero={h} />)}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire in App.tsx**

Replace `{ path: 'summon', element: <Stub name="Summon" /> }` with:
```tsx
{ path: 'summon', element: <SummonRoute /> },
```
Add import: `import { SummonRoute } from './routes/Summon'`

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Summon tab with pity bar, pull buttons, last-pull grid"
```

---

### Task 6: Shop tab

**Files:**
- Create: `frontend/src/api/shop.ts`
- Create: `frontend/src/routes/Shop.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create shop API**

```typescript
// frontend/src/api/shop.ts
import type { ShopProduct } from '../types'
import { apiFetch, apiPost } from './client'

interface ShopData {
  products: ShopProduct[]
  starter: ShopProduct | null
  history: PurchaseHistory[]
  shard_exchange: ShardExchange
}

export interface PurchaseHistory {
  id: number
  title: string
  sku: string
  state: string
  price_cents: number
  created_at: string
  granted_short: string
}

export interface ShardExchange {
  gems_per_batch: number
  shards_per_batch: number
  max_per_day: number
  used_today: number
  remaining_today: number
}

export const fetchShop = (): Promise<ShopData> => apiFetch('/app/partials/shop-data')

export const buyProduct = (sku: string): Promise<{ granted: Record<string, unknown> }> =>
  apiPost('/shop/buy', { sku })

export const exchangeShards = (): Promise<{ shards_granted: number }> =>
  apiPost('/shop/shard-exchange', {})
```

**Note:** The `/app/partials/shop-data` endpoint doesn't exist as pure JSON yet. Use the existing shop partial data by calling the shop JSON endpoints directly. Replace `fetchShop` implementation with:

```typescript
// frontend/src/api/shop.ts (corrected)
import type { ShopProduct } from '../types'
import { apiFetch, apiPost } from './client'

export interface PurchaseHistory {
  id: number; title: string; sku: string; state: string
  price_cents: number; created_at: string; granted_short: string
}
export interface ShardExchange {
  gems_per_batch: number; shards_per_batch: number
  max_per_day: number; used_today: number; remaining_today: number
}
export interface ShopData {
  products: ShopProduct[]; starter: ShopProduct | null
  history: PurchaseHistory[]; shard_exchange: ShardExchange
}

export const fetchShop = (): Promise<ShopData> => apiFetch<ShopData>('/shop')
export const buyProduct = (sku: string, stripe_token?: string): Promise<{ granted: Record<string, unknown> }> =>
  apiPost('/shop/buy', { sku, ...(stripe_token ? { stripe_token } : {}) })
export const exchangeShards = (): Promise<{ shards_granted: number }> =>
  apiPost('/shop/shard-exchange', {})
```

- [ ] **Step 2: Create Shop route**

```tsx
// frontend/src/routes/Shop.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchShop, buyProduct, exchangeShards } from '../api/shop'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { useState } from 'react'

export function ShopRoute() {
  const qc = useQueryClient()
  const { data: shop, isLoading } = useQuery({
    queryKey: ['shop'], queryFn: fetchShop, staleTime: 2 * 60_000,
  })
  const [buying, setBuying] = useState<string | null>(null)
  const [exchanging, setExchanging] = useState(false)

  if (isLoading) return <SkeletonGrid count={6} height={100} />
  if (!shop) return <div className="muted">Shop unavailable.</div>

  async function buy(sku: string) {
    setBuying(sku)
    try {
      const res = await buyProduct(sku)
      const parts = Object.entries(res.granted ?? {}).filter(([, v]) => Number(v) > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Purchased! ${parts.join(', ')}` : 'Purchased!')
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Purchase failed')
    } finally {
      setBuying(null) }
  }

  async function doExchange() {
    setExchanging(true)
    try {
      const res = await exchangeShards()
      toast.success(`+${res.shards_granted} shards!`)
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Exchange failed')
    } finally {
      setExchanging(false) }
  }

  const sx = shop.shard_exchange

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Shop</h2>

      {/* Shard exchange */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Gem → Shard Exchange</h3>
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
          {sx.gems_per_batch} 💎 → {sx.shards_per_batch} ✦ shards · {sx.remaining_today}/{sx.max_per_day} trades left today
        </div>
        <button
          className="primary"
          onClick={doExchange}
          disabled={exchanging || sx.remaining_today <= 0}
        >
          {exchanging ? '…' : `Trade ${sx.gems_per_batch} 💎 for ${sx.shards_per_batch} ✦`}
        </button>
      </div>

      {/* Starter bundle */}
      {shop.starter && (
        <div className="card" style={{ border: '1px solid var(--r-legendary)', background: 'rgba(255,216,107,0.05)' }}>
          <div style={{ fontSize: 11, color: 'var(--r-legendary)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
            ⭐ Starter Bundle
          </div>
          <div style={{ fontWeight: 700 }}>{shop.starter.title}</div>
          <div className="muted" style={{ fontSize: 12, margin: '4px 0 10px' }}>{shop.starter.description}</div>
          <button className="primary" onClick={() => buy(shop.starter!.sku)} disabled={!!buying}>
            {buying === shop.starter.sku ? '…' : `$${(shop.starter.price_cents / 100).toFixed(2)}`}
          </button>
        </div>
      )}

      {/* Product grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {shop.products.map((p) => (
          <div key={p.sku} className="card">
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{p.title}</div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{p.description}</div>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, color: 'var(--warn)' }}>
                {p.price_cents === 0 ? 'Free' : `$${(p.price_cents / 100).toFixed(2)}`}
              </span>
              <button
                className="primary"
                style={{ fontSize: 12 }}
                onClick={() => buy(p.sku)}
                disabled={!!buying}
              >
                {buying === p.sku ? '…' : 'Buy'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Purchase history */}
      {shop.history.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent Purchases</h3>
          <div className="stack" style={{ gap: 6 }}>
            {shop.history.map((h) => (
              <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span>{h.title}</span>
                <span className="muted">{h.granted_short}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire in App.tsx**

Replace `{ path: 'shop', element: <Stub name="Shop" /> }` with:
```tsx
{ path: 'shop', element: <ShopRoute /> },
```
Add import: `import { ShopRoute } from './routes/Shop'`

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Shop tab with product grid, shard exchange, purchase history"
```

---

### Task 7: Full test run + verify

- [ ] **Step 1: Run all frontend tests**

```bash
cd frontend && npx vitest run
```
Expected: all tests pass.

- [ ] **Step 2: TypeScript check**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Python test suite still green**

```bash
cd .. && pytest -q
```
Expected: 634 passed, 3 skipped.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: SPA Plan 2 complete — Me, Roster, HeroDetail, Stages, Summon, Shop"
```

---

**Plan 2 complete.** Next: `2026-04-27-spa-p3-remaining-tabs.md` — Guild, Friends, Arena, Raids, Daily, Story, Achievements, Event, Crafting, Account.
