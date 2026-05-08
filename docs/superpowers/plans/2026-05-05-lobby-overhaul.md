# Lobby Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat card-grid lobby with a three-column dark cyberpunk + dark fantasy UI featuring The Rootlord as a reactive mascot, zone-tab navigation, and three-tab shop (Coins / Gems / QoL).

**Architecture:** `tokens.css` gets a full new color system; `Shell.tsx` drops its maxWidth constraint on `/app/me`; `Me.tsx` becomes a self-contained three-column layout (Rootlord sidebar | zone tabs + content | shop + live log); `Shop.tsx` becomes a standalone three-tab page. Backend gets new `COIN_PACK` kind and coin/QoL seed products.

**Tech Stack:** React 18, React Router v6, TanStack Query v5, FastAPI, SQLAlchemy, Alembic, SQLite (dev)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/styles/tokens.css` | Modify | New color system: teal/crimson/gold/purple dark palette |
| `frontend/src/styles/global.css` | Modify | Scanline overlay, updated nav-tab active style, new utility classes |
| `frontend/src/components/Layout/Shell.tsx` | Modify | Remove maxWidth/padding on `/app/me`; keep NavBar for other routes |
| `frontend/src/components/Layout/RootlordSidebar.tsx` | Create | Rootlord card art + rotating reactive terminal quote |
| `frontend/src/routes/Me.tsx` | Rewrite | Three-column layout: sidebar + zone tabs (6 sectors) + right panel |
| `frontend/src/routes/Shop.tsx` | Rewrite | Three-tab shop: Coins / Gems / QoL |
| `frontend/src/api/shop.ts` | Modify | Add `fetchShopByKind()` helper, export kind constants |
| `app/models.py` | Modify | Add `COIN_PACK` to `ShopProductKind` enum |
| `app/seed.py` | Modify | Add coin SKUs + daily free coin sack product |
| `alembic/versions/` | Create | Migration: no schema change needed (enum is a string column) |

---

## Task 1: Update Design Tokens

**Files:**
- Modify: `frontend/src/styles/tokens.css`

- [ ] **Step 1.1: Replace tokens.css**

```css
/* frontend/src/styles/tokens.css */
:root {
  /* ── Dark cyberpunk base ── */
  --bg:        #04060c;
  --bg-inset:  #080d18;
  --panel:     #0c101a;
  --panel-2:   #10141f;
  --border:    rgba(0, 255, 224, 0.08);
  --text:      #dde4f0;
  --muted:     #4a5a72;

  /* ── Cyberpunk accents ── */
  --accent:    #00ffe0;
  --magenta:   #ff2d78;

  /* ── Dark fantasy (character / rarity) ── */
  --crimson:   #c8102e;
  --gold:      #ffd700;
  --void-purple: #9b30ff;

  /* ── Semantic ── */
  --good:  #22c55e;
  --bad:   #ef4444;
  --warn:  #f59e0b;

  /* ── Rarity ── */
  --r-common:    #9ca7b3;
  --r-uncommon:  #22c55e;
  --r-rare:      #00ffe0;
  --r-epic:      #9b30ff;
  --r-legendary: #ffd700;
  --r-myth:      #c8102e;

  /* ── Faction ── */
  --faction-resistance: #22c55e;
  --faction-corp-greed: #9b30ff;
  --faction-exile:      #ffd700;
  --faction-neutral:    #9ca7b3;

  /* ── Role ── */
  --role-atk: #ff2d78;
  --role-def: #00ffe0;
  --role-sup: #22c55e;

  /* ── Spacing ── */
  --radius:    6px;
  --radius-sm: 4px;
  --radius-lg: 10px;
}
```

- [ ] **Step 1.2: Add scanline overlay + nav-tab restyle to global.css**

Find the line `body {` at the top of `global.css` and add `::before` scanline after the body block:

```css
/* Add immediately after the closing `}` of the `body {}` rule */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 255, 224, 0.012) 2px,
    rgba(0, 255, 224, 0.012) 3px
  );
  pointer-events: none;
  z-index: 9999;
}
```

- [ ] **Step 1.3: Restyle `.nav-tab.is-active` in global.css**

Replace the existing `.nav-tab.is-active` block:

```css
.nav-tab.is-active {
  background: rgba(0, 255, 224, 0.1);
  color: var(--accent);
  font-weight: 700;
  border-color: rgba(0, 255, 224, 0.4);
  box-shadow: 0 0 12px rgba(0, 255, 224, 0.15);
  text-shadow: 0 0 8px rgba(0, 255, 224, 0.5);
}
.nav-tab.is-active:hover {
  background: rgba(0, 255, 224, 0.14);
  border-color: rgba(0, 255, 224, 0.5);
  color: var(--accent);
}
.nav-tab.is-active .nav-tab-badge {
  background: var(--accent);
  color: #000;
  box-shadow: 0 0 0 2px rgba(0, 255, 224, 0.3);
}
```

- [ ] **Step 1.4: Add utility classes to bottom of global.css**

```css
/* ── Lobby utilities ── */
.teal-glow   { text-shadow: 0 0 8px rgba(0, 255, 224, 0.6); }
.crimson-glow { text-shadow: 0 0 10px rgba(200, 16, 46, 0.7); }
.label-caps {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
}
.meter-bar {
  height: 5px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}
.meter-fill {
  height: 100%;
  border-radius: 3px;
}
```

- [ ] **Step 1.5: Start dev server and verify dark background renders**

```bash
cd C:/Users/User/.claude/mmorpg/hero-proto
npm --prefix frontend run dev
```

Open `http://localhost:5173/app/login` — background should be near-black (`#04060c`), accent color should be teal (`#00ffe0`). Check that existing routes (Roster, Arena) still render without broken layouts.

- [ ] **Step 1.6: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/styles/global.css
git commit -m "style: dark cyberpunk token overhaul — teal/crimson/gold palette"
```

---

## Task 2: Create RootlordSidebar Component

**Files:**
- Create: `frontend/src/components/Layout/RootlordSidebar.tsx`

The sidebar shows The Rootlord card art (faded at bottom), a rotating reactive quote in terminal style, and the character title. It reads account state from the `me` query to pick state-driven quotes.

- [ ] **Step 2.1: Create the component**

```tsx
// frontend/src/components/Layout/RootlordSidebar.tsx
import { useEffect, useState } from 'react'
import { useMe } from '../../hooks/useMe'
import { useQuery } from '@tanstack/react-query'
import { fetchDaily } from '../../api/daily'

const DEFAULT_QUOTES = [
  'The ticket queue never sleeps.',
  'sudo rm -rf /your-excuses --no-preserve-root',
  'GODMODE isn\'t a cheat code. It\'s a career.',
  'Change request denied. Reality can\'t be reverted.',
  'I break things so you understand what\'s worth keeping.',
  'Monitoring is for the weak. I depend on chaos.',
  'Best practices are suggestions. I deleted the document.',
]

function pickQuote(
  me: { energy: number; energy_cap: number; arena_wins: number; arena_losses: number } | undefined,
  unclaimed: number,
  pullsSinceEpic: number,
): string {
  if (!me) return DEFAULT_QUOTES[0]
  const energyPct = me.energy / me.energy_cap
  if (energyPct <= 0.2) return 'Energy critical. sudo reboot self.'
  if (unclaimed >= 2) return 'Resources unclaimed. This is how entropy starts.'
  if (pullsSinceEpic >= 45) return 'The pity counter nears its limit. It knows what\'s coming.'
  if (me.arena_losses > me.arena_wins && me.arena_wins + me.arena_losses > 0)
    return 'The metrics lie. Purge the metrics.'
  const idx = Math.floor(Date.now() / 6000) % DEFAULT_QUOTES.length
  return DEFAULT_QUOTES[idx]
}

export function RootlordSidebar() {
  const { data: me } = useMe()
  const { data: daily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily, staleTime: 60_000 })
  const [quote, setQuote] = useState('')
  const [visible, setVisible] = useState(true)

  const unclaimed = (daily ?? []).filter((q) => q.status === 'COMPLETE').length

  useEffect(() => {
    const next = pickQuote(me, unclaimed, me?.pulls_since_epic ?? 0)
    setQuote(next)
    const id = setInterval(() => {
      setVisible(false)
      setTimeout(() => {
        setQuote(pickQuote(me, unclaimed, me?.pulls_since_epic ?? 0))
        setVisible(true)
      }, 350)
    }, 6000)
    return () => clearInterval(id)
  }, [me, unclaimed])

  return (
    <aside style={{
      width: 220,
      flexShrink: 0,
      background: 'linear-gradient(180deg, #0a0208 0%, var(--bg) 60%)',
      borderRight: '1px solid rgba(200, 16, 46, 0.2)',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* crimson radial glow at top */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        height: 280,
        background: 'radial-gradient(ellipse at 50% 0%, rgba(200,16,46,0.2) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* animated right border */}
      <div style={{
        position: 'absolute',
        top: 0, bottom: 0, right: 0,
        width: 1,
        background: 'linear-gradient(180deg, transparent, rgba(200,16,46,0.5), rgba(0,255,224,0.2), transparent)',
        pointerEvents: 'none',
      }} />

      {/* Card art */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <img
          src="/app/static/heroes/cards/The_Man_The_Dev.png"
          alt="The Rootlord"
          style={{
            width: '100%',
            display: 'block',
            maskImage: 'linear-gradient(180deg, black 50%, transparent 86%)',
            WebkitMaskImage: 'linear-gradient(180deg, black 50%, transparent 86%)',
            filter: 'drop-shadow(0 0 24px rgba(200,16,46,0.5))',
          }}
          onError={(e) => {
            ;(e.target as HTMLImageElement).style.display = 'none'
          }}
        />
      </div>

      {/* Terminal output */}
      <div style={{
        flex: 1,
        padding: '10px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        position: 'relative',
        zIndex: 1,
        fontFamily: "'Consolas', 'Courier New', monospace",
      }}>
        <div style={{ fontSize: 10, color: 'var(--muted)' }}>
          <span style={{ color: 'var(--crimson)' }}>root@void:~$</span>
          {' '}
          <span style={{ color: 'rgba(0,255,224,0.5)' }}>status</span>
        </div>

        <div style={{
          fontSize: 11,
          color: '#8a7a60',
          fontStyle: 'italic',
          lineHeight: 1.5,
          marginTop: 2,
          opacity: visible ? 1 : 0,
          transition: 'opacity 0.35s',
          minHeight: 48,
        }}>
          {quote}
        </div>

        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
          <span style={{ color: 'var(--crimson)' }}>root@void:~$</span>
          {' '}
          <span style={{
            display: 'inline-block',
            width: 7, height: 12,
            background: 'var(--accent)',
            verticalAlign: 'middle',
            boxShadow: '0 0 6px var(--accent)',
            animation: 'cursor-blink 1s step-start infinite',
          }} />
        </div>

        <div style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: '1px solid rgba(255,255,255,0.04)',
          fontSize: 10,
          color: 'rgba(200,16,46,0.7)',
          fontWeight: 700,
          letterSpacing: '0.1em',
        }}>
          ◈ THE ROOTLORD
        </div>
        <div style={{ fontSize: 9, color: 'rgba(138,122,96,0.6)', fontStyle: 'italic' }}>
          MYTH · ROGUE_IT · DEVOPS
        </div>
        <div style={{ fontSize: 9, color: 'rgba(100,100,120,0.5)', marginTop: 2 }}>
          He doesn't follow best practices.
        </div>
        <div style={{ fontSize: 9, color: 'rgba(100,100,120,0.5)' }}>
          He deletes them.
        </div>
      </div>
    </aside>
  )
}
```

- [ ] **Step 2.2: Add cursor-blink keyframe to global.css**

```css
@keyframes cursor-blink {
  50% { opacity: 0; }
}
```

- [ ] **Step 2.3: Commit**

```bash
git add frontend/src/components/Layout/RootlordSidebar.tsx frontend/src/styles/global.css
git commit -m "feat: RootlordSidebar component with reactive terminal quotes"
```

---

## Task 3: Update Shell for Full-Viewport Me Route

**Files:**
- Modify: `frontend/src/components/Layout/Shell.tsx`

On `/app/me`, the main content should be full-width (no maxWidth, no padding) so `Me.tsx` can control its own layout. All other routes keep the existing constrained layout.

- [ ] **Step 3.1: Modify Shell.tsx**

Replace the entire file:

```tsx
// frontend/src/components/Layout/Shell.tsx
import { useEffect, useRef } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { NavBar } from './NavBar'
import { CurrencyBar } from './CurrencyBar'
import { ToastContainer } from '../Toast'
import { AgeGate } from '../AgeGate'
import { VersionTag } from '../VersionTag'
import { useAuthStore } from '../../store/auth'
import { initPush } from '../../api/push'

const PUBLIC_PATHS = new Set(['/app/login', '/app/privacy', '/app/terms'])

export function Shell() {
  const jwt = useAuthStore((s) => s.jwt)
  const location = useLocation()
  const pushInitialized = useRef(false)
  const isLobby = location.pathname === '/app/me' || location.pathname === '/app/'

  useEffect(() => {
    if (jwt && !pushInitialized.current) {
      pushInitialized.current = true
      initPush().catch(() => {/* push is non-critical */})
    }
    if (!jwt) pushInitialized.current = false
  }, [jwt])

  if (!jwt && !PUBLIC_PATHS.has(location.pathname)) {
    return <Navigate to="/app/login" replace state={{ from: location }} />
  }

  if (isLobby) {
    return (
      <AgeGate>
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Outlet />
          <ToastContainer />
        </div>
      </AgeGate>
    )
  }

  return (
    <AgeGate>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <NavBar />
        <CurrencyBar />
        <main className="main-content" style={{ padding: 18, maxWidth: 1100, margin: '0 auto', width: '100%', flex: 1 }}>
          <Outlet />
        </main>
        <ToastContainer />
        <VersionTag />
      </div>
    </AgeGate>
  )
}
```

- [ ] **Step 3.2: Verify the shell renders correctly**

Navigate to `/app/me` — the NavBar and CurrencyBar should be gone (full viewport). Navigate to `/app/roster` — NavBar and CurrencyBar should still be present.

- [ ] **Step 3.3: Commit**

```bash
git add frontend/src/components/Layout/Shell.tsx
git commit -m "feat: full-viewport shell on /app/me route"
```

---

## Task 4: Rewrite Me.tsx — Three-Column Lobby

**Files:**
- Modify: `frontend/src/routes/Me.tsx`

This is the main lobby: Rootlord sidebar (220px) | zone tabs + content (flex 1) | shop + log panel (280px).

- [ ] **Step 4.1: Replace Me.tsx entirely**

```tsx
// frontend/src/routes/Me.tsx
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { fetchDaily } from '../api/daily'
import { fetchShop, buyProduct, exchangeShards } from '../api/shop'
import { apiPost } from '../api/client'
import { toast } from '../store/ui'
import { RootlordSidebar } from '../components/Layout/RootlordSidebar'
import { RarityPill } from '../components/RarityPill'
import { useAuthStore } from '../store/auth'

// ── Top bar ──────────────────────────────────────────────────────────────────

function TopBar() {
  const { data: me } = useMe()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const [clock, setClock] = useState('')

  useEffect(() => {
    const tick = () => setClock(new Date().toTimeString().slice(0, 8))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  function logout() {
    clearJwt()
    qc.clear()
    window.location.href = '/'
  }

  return (
    <div style={{
      height: 44,
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '0 16px',
      background: 'rgba(4,6,12,0.95)',
      borderBottom: '1px solid rgba(0,255,224,0.06)',
      flexShrink: 0,
      zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--good)',
          boxShadow: '0 0 6px var(--good)',
          animation: 'cursor-blink 2s infinite',
        }} />
        <span style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
          color: 'var(--accent)',
          textShadow: '0 0 10px rgba(0,255,224,0.6)',
          fontFamily: 'Consolas, monospace',
        }}>
          SYSTEM::HERO-PROTO
        </span>
      </div>

      {me && (
        <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'Consolas, monospace', letterSpacing: '0.06em' }}>
          USER <span style={{ color: 'rgba(0,255,224,0.6)' }}>{me.email.split('@')[0]}</span>
          {' | '}LVL <span style={{ color: 'var(--accent)' }}>{me.account_level}</span>
          {' | '}{me.faction === 'RESISTANCE' ? '📡' : me.faction === 'CORP_GREED' ? '📈' : '🌑'} {me.faction}
        </span>
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        {me && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, fontWeight: 700 }}>
            <span style={{ color: 'var(--accent)' }}>💎 {me.gems.toLocaleString()}</span>
            <span style={{ color: 'var(--gold)' }}>🪙 {me.coins.toLocaleString()}</span>
            <span style={{ color: 'var(--void-purple)' }}>✦ {me.shards.toLocaleString()}</span>
            <span style={{ color: 'var(--good)' }}>⚡ {me.energy}/{me.energy_cap}</span>
          </div>
        )}
        <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'Consolas, monospace', paddingLeft: 12, borderLeft: '1px solid rgba(255,255,255,0.06)' }}>
          {clock}
        </span>
        <button
          onClick={logout}
          style={{
            fontSize: 11, padding: '4px 10px', borderRadius: 4,
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            color: 'var(--muted)', cursor: 'pointer', fontWeight: 600,
          }}
        >
          ⏻
        </button>
      </div>
    </div>
  )
}

// ── Zone tabs ─────────────────────────────────────────────────────────────────

type Zone = 'ops' | 'combat' | 'summon' | 'story' | 'guild' | 'raid'

const ZONES: { id: Zone; icon: string; label: string }[] = [
  { id: 'ops',    icon: '⬡', label: 'Ops'    },
  { id: 'combat', icon: '⚔', label: 'Combat' },
  { id: 'summon', icon: '🌀', label: 'Summon' },
  { id: 'story',  icon: '📖', label: 'Story'  },
  { id: 'guild',  icon: '🛡', label: 'Guild'  },
  { id: 'raid',   icon: '🐉', label: 'Raid'   },
]

// ── Sector: Ops ───────────────────────────────────────────────────────────────

function OpsPanel() {
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: daily, refetch: refetchDaily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily, staleTime: 30_000 })
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [claiming, setClaiming] = useState(false)
  const [claimingBonus, setClaimingBonus] = useState(false)

  if (!me) return null

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'
  const pityPct = Math.min(100, (me.pulls_since_epic / 50) * 100)
  const claimable = (daily ?? []).filter((q) => q.status === 'COMPLETE')
  const claimed = (daily ?? []).filter((q) => q.status === 'CLAIMED').length
  const total = daily?.length ?? 0

  const RARITY_ORDER = ['MYTH','LEGENDARY','EPIC','RARE','UNCOMMON','COMMON']
  const topHeroes = [...(heroes ?? [])]
    .sort((a, b) => RARITY_ORDER.indexOf(a.template.rarity) - RARITY_ORDER.indexOf(b.template.rarity) || b.power - a.power)
    .slice(0, 6)

  async function claimAll() {
    setClaiming(true)
    for (const q of claimable) {
      try { await apiPost(`/daily/${q.id}/claim`, {}) } catch {}
    }
    await qc.invalidateQueries({ queryKey: ['daily'] })
    await qc.invalidateQueries({ queryKey: ['me'] })
    refetchDaily()
    toast.success(`Claimed ${claimable.length} reward${claimable.length !== 1 ? 's' : ''}!`)
    setClaiming(false)
  }

  async function claimDailyBonus() {
    setClaimingBonus(true)
    try {
      const res = await apiPost<{ reward: Record<string, number> }>('/me/daily-bonus', {})
      const parts = Object.entries(res.reward).filter(([, v]) => v > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Daily bonus: ${parts.join(', ')}` : 'Claimed!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setClaimingBonus(false) }
  }

  const ActionTile = ({ icon, label, path, color, badge }: { icon: string; label: string; path: string; color: string; badge?: string }) => (
    <div
      role="button" tabIndex={0}
      onClick={() => navigate(path)}
      onKeyDown={(e) => e.key === 'Enter' && navigate(path)}
      style={{
        background: 'var(--panel-2)',
        border: `1px solid rgba(0,255,224,0.06)`,
        borderRadius: 8,
        padding: '18px 10px',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'all 0.2s',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = color
        el.style.transform = 'translateY(-2px)'
        el.style.boxShadow = `0 6px 24px rgba(0,0,0,0.5)`
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = 'rgba(0,255,224,0.06)'
        el.style.transform = 'translateY(0)'
        el.style.boxShadow = 'none'
      }}
    >
      {badge && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          background: 'var(--magenta)', color: '#fff',
          fontSize: 9, fontWeight: 900, padding: '1px 5px', borderRadius: 2,
        }}>{badge}</div>
      )}
      <div style={{ fontSize: 28, marginBottom: 6 }}>{icon}</div>
      <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--muted)' }}>{label}</div>
    </div>
  )

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, height: '100%' }}>
      {/* Left: command matrix + status */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', paddingRight: 4 }}>
        {/* Player strip */}
        <div style={{
          background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)',
          borderRadius: 8, padding: '14px 16px',
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 6, flexShrink: 0,
            background: 'linear-gradient(135deg, rgba(0,255,224,0.2), rgba(155,48,255,0.2))',
            border: '1px solid rgba(0,255,224,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 900, color: 'var(--accent)',
            boxShadow: '0 0 12px rgba(0,255,224,0.15)',
          }}>
            {me.email.slice(0, 2).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>{me.email.split('@')[0]}</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
              Arena {me.arena_rating} · {heroes?.length ?? 0} Heroes · {me.stages_cleared.length} Stages
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 3 }}>
              Lv {me.account_level} · {me.account_xp.toLocaleString()} XP
            </div>
            <div style={{ width: 120, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(100, (me.account_xp % 500) / 5)}%`, background: 'linear-gradient(90deg, var(--accent), var(--void-purple))', borderRadius: 2 }} />
            </div>
          </div>
        </div>

        {/* Command matrix */}
        <div>
          <div className="label-caps" style={{ marginBottom: 8 }}>Command Matrix</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            <ActionTile icon="⚔️" label="Battle"  path="/app/stages" color="var(--magenta)" />
            <ActionTile icon="🌀" label="Summon"  path="/app/summon" color="var(--void-purple)" badge={me.free_summon_credits > 0 ? String(me.free_summon_credits) : undefined} />
            <ActionTile icon="🏟️" label="Arena"   path="/app/arena"  color="var(--warn)" />
            <ActionTile icon="🐉" label="Raid"    path="/app/raids"  color="var(--gold)" />
            <ActionTile icon="🛡️" label="Guild"   path="/app/guild"  color="var(--accent)" />
            <ActionTile icon="📖" label="Story"   path="/app/story"  color="var(--r-epic)" />
          </div>
        </div>

        {/* Status meters */}
        <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
          <div className="label-caps" style={{ marginBottom: 12 }}>System Status</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { label: '⚡ Energy', value: `${me.energy} / ${me.energy_cap}`, pct: energyPct / 100, color: energyColor },
              { label: '🌀 Pity Counter', value: `${me.pulls_since_epic} / 50`, pct: pityPct / 100, color: 'var(--void-purple)' },
              { label: '🏟️ Arena Rating', value: String(me.arena_rating), pct: Math.min(1, me.arena_rating / 4000), color: 'var(--warn)' },
            ].map(({ label, value, pct, color }) => (
              <div key={label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--muted)' }}>{label}</span>
                  <span style={{ fontWeight: 700, color }}>{value}</span>
                </div>
                <div className="meter-bar">
                  <div className="meter-fill" style={{ width: `${pct * 100}%`, background: color, boxShadow: `0 0 6px ${color}60` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top heroes */}
        {topHeroes.length > 0 && (
          <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="label-caps">Top Heroes</div>
              <button onClick={() => navigate('/app/roster')} style={{ fontSize: 10, padding: '3px 8px', color: 'var(--accent)', background: 'transparent', border: '1px solid rgba(0,255,224,0.2)', borderRadius: 4 }}>
                View All →
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {topHeroes.map((h) => (
                <div
                  key={h.id}
                  role="button" tabIndex={0}
                  onClick={() => navigate(`/app/roster/${h.id}`)}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/app/roster/${h.id}`)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 10px', borderRadius: 6,
                    background: 'var(--bg-inset)', cursor: 'pointer',
                    border: '1px solid transparent', transition: 'border-color 0.15s',
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(0,255,224,0.12)' }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'transparent' }}
                >
                  <img
                    src={`/app/static/heroes/busts/${h.template.code}.png`}
                    alt={h.template.name}
                    style={{ width: 32, height: 32, borderRadius: 4, objectFit: 'cover', background: 'var(--panel-2)' }}
                    onError={(e) => { (e.target as HTMLImageElement).src = `/app/placeholder/hero/${h.template.code}.svg` }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {'⭐'.repeat(Math.min(h.stars, 3))}{h.stars > 3 ? `+${h.stars - 3}` : ''} {h.template.name}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>Lv {h.level} · ⚡ {h.power.toLocaleString()}</div>
                  </div>
                  <RarityPill rarity={h.template.rarity} size="sm" />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: daily quests + login bonus */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {/* Daily login bonus */}
        <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(200,16,46,0.2)', borderRadius: 8, padding: '14px 16px' }}>
          <div className="label-caps" style={{ marginBottom: 10 }}>🎁 Daily Login</div>
          <button
            onClick={claimDailyBonus} disabled={claimingBonus}
            style={{
              width: '100%', padding: 8, border: '1px solid rgba(200,16,46,0.4)',
              borderRadius: 4, background: 'rgba(200,16,46,0.12)',
              color: 'var(--crimson)', fontWeight: 900, fontSize: 11,
              letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
            }}
          >
            {claimingBonus ? '…' : 'Claim Daily Bonus'}
          </button>
        </div>

        {/* Daily ops */}
        {daily && (
          <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px', flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="label-caps">📋 Daily Ops</div>
              <span style={{ fontSize: 10, color: 'var(--good)' }}>{claimed}/{total}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {daily.map((q) => {
                const dotColor = q.status === 'CLAIMED' ? 'var(--good)' : q.status === 'COMPLETE' ? 'var(--accent)' : 'var(--muted)'
                return (
                  <div key={q.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor, marginTop: 4, flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11, color: q.status === 'CLAIMED' ? 'var(--muted)' : 'var(--text)' }}>
                        {q.kind.replace(/_/g, ' ')}
                      </div>
                      <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginTop: 4, overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: dotColor, width: `${Math.min(100, (q.progress / q.goal) * 100)}%` }} />
                      </div>
                    </div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--warn)', flexShrink: 0 }}>
                      {q.reward_gems > 0 ? `💎${q.reward_gems}` : ''}{q.reward_coins > 0 ? `🪙${q.reward_coins}` : ''}
                    </div>
                  </div>
                )
              })}
            </div>
            {claimable.length > 0 && (
              <button
                onClick={claimAll} disabled={claiming}
                className="primary"
                style={{ marginTop: 10, width: '100%', fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                {claiming ? '…' : `Claim ${claimable.length} Ready`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Sector stubs (link out) ───────────────────────────────────────────────────

function CombatPanel() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  if (!me) return null
  const winRate = me.arena_wins + me.arena_losses > 0
    ? Math.round((me.arena_wins / (me.arena_wins + me.arena_losses)) * 100) : null
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      {[
        { label: 'Arena Rating', value: me.arena_rating, color: 'var(--warn)' },
        { label: 'Wins', value: me.arena_wins, color: 'var(--good)' },
        { label: 'Losses', value: me.arena_losses, color: 'var(--bad)' },
        { label: 'Win Rate', value: winRate !== null ? `${winRate}%` : '—', color: winRate !== null && winRate >= 50 ? 'var(--good)' : 'var(--bad)' },
        { label: 'Stages Cleared', value: me.stages_cleared.length, color: 'var(--accent)' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 6 }}>{label}</div>
          <div style={{ fontSize: 28, fontWeight: 900, color }}>{value}</div>
        </div>
      ))}
      <button onClick={() => navigate('/app/arena')} className="primary" style={{ gridColumn: '1/-1', padding: 10, fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        ⚔ Enter Arena
      </button>
    </div>
  )
}

function SummonPanel() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  if (!me) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {[
        { label: '🌀 Pity Counter', value: `${me.pulls_since_epic} / 50`, color: 'var(--void-purple)' },
        { label: '🎟️ Free Credits', value: me.free_summon_credits, color: 'var(--r-epic)' },
        { label: '🎫 Access Cards', value: me.access_cards, color: 'var(--text)' },
        { label: '💎 Gems Available', value: me.gems.toLocaleString(), color: 'var(--accent)' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>{label}</span>
          <span style={{ fontSize: 14, fontWeight: 800, color }}>{value}</span>
        </div>
      ))}
      <button onClick={() => navigate('/app/summon')} className="primary" style={{ padding: 10, fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        🌀 Initiate Summon
      </button>
    </div>
  )
}

function StubPanel({ label, path }: { label: string; path: string }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, height: '100%', color: 'var(--muted)' }}>
      <div style={{ fontSize: 48 }}>{label.split(' ')[0]}</div>
      <div style={{ fontSize: 13 }}>{label}</div>
      <button onClick={() => navigate(path)} className="primary">Go →</button>
    </div>
  )
}

// ── Right panel: shop + event log ─────────────────────────────────────────────

type ShopTab = 'coins' | 'gems' | 'qol'

function RightPanel() {
  const { data: me } = useMe()
  const { data: shop } = useQuery({ queryKey: ['shop'], queryFn: fetchShop, staleTime: 2 * 60_000 })
  const qc = useQueryClient()
  const [shopTab, setShopTab] = useState<ShopTab>('coins')
  const [buying, setBuying] = useState<string | null>(null)
  const [exchanging, setExchanging] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  const LOG_TAGS: { tag: string; color: string; msg: string }[] = [
    { tag: '[ARENA]',  color: 'var(--good)',        msg: 'WIN vs shadowkill_99 +12'       },
    { tag: '[SUMMON]', color: 'var(--void-purple)',  msg: 'Pulled: Netrunner [RARE]'       },
    { tag: '[GUILD]',  color: 'var(--accent)',       msg: 'Guild contribution recorded'    },
    { tag: '[ARENA]',  color: 'var(--bad)',          msg: 'LOSS vs DevNull404 -8'          },
    { tag: '[RAID]',   color: 'var(--gold)',         msg: 'Contributed 2,400 dmg to boss'  },
    { tag: '[QUEST]',  color: 'var(--good)',         msg: 'Daily quest completed'           },
  ]
  const [logEntries, setLogEntries] = useState(LOG_TAGS.slice(0, 4))
  const logIdx = useRef(4)

  useEffect(() => {
    const id = setInterval(() => {
      const entry = LOG_TAGS[logIdx.current % LOG_TAGS.length]
      logIdx.current++
      setLogEntries((prev) => [entry, ...prev].slice(0, 8))
    }, 9000)
    return () => clearInterval(id)
  }, [])

  async function buy(sku: string) {
    setBuying(sku)
    try {
      const res = await buyProduct(sku)
      const parts = Object.entries(res.granted ?? {}).filter(([, v]) => Number(v) > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Purchased! ${parts.join(', ')}` : 'Purchased!')
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Purchase failed') }
    finally { setBuying(null) }
  }

  async function doExchange() {
    setExchanging(true)
    try {
      const res = await exchangeShards()
      toast.success(`+${res.shards_granted} shards!`)
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Exchange failed') }
    finally { setExchanging(false) }
  }

  if (!me) return null

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'

  const gemProducts = (shop?.products ?? []).filter((p) => p.kind === 'GEM_PACK')
  const coinProducts = (shop?.products ?? []).filter((p) => p.kind === 'COIN_PACK')
  const qolProducts = (shop?.products ?? []).filter((p) => p.kind?.startsWith('QOL') || p.kind === 'WEEKLY_BUNDLE')

  const sx = shop?.shard_exchange

  return (
    <div style={{
      width: 280, flexShrink: 0,
      borderLeft: '1px solid rgba(0,255,224,0.06)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>

        {/* Energy mini */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>
            <span>⚡ Energy</span>
            <span style={{ fontWeight: 700, color: energyColor }}>{me.energy} / {me.energy_cap}</span>
          </div>
          <div className="meter-bar">
            <div className="meter-fill" style={{ width: `${energyPct}%`, background: energyColor, boxShadow: `0 0 4px ${energyColor}60` }} />
          </div>
        </div>

        <div style={{ height: 1, background: 'rgba(0,255,224,0.05)' }} />

        {/* Shop tabs */}
        <div className="label-caps">Shop</div>
        <div style={{ display: 'flex', gap: 3 }}>
          {(['coins', 'gems', 'qol'] as ShopTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setShopTab(t)}
              style={{
                flex: 1, padding: '5px 4px', fontSize: 9, fontWeight: 800,
                letterSpacing: '0.08em', textTransform: 'uppercase',
                border: '1px solid',
                borderColor: shopTab === t ? 'rgba(0,255,224,0.4)' : 'rgba(0,255,224,0.06)',
                borderRadius: 4,
                background: shopTab === t ? 'rgba(0,255,224,0.08)' : 'var(--panel-2)',
                color: shopTab === t ? 'var(--accent)' : 'var(--muted)',
                cursor: 'pointer',
              }}
            >
              {t === 'coins' ? '🪙' : t === 'gems' ? '💎' : '⚙️'} {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* Shop items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {shopTab === 'coins' && coinProducts.map((p) => (
            <ShopItem key={p.sku} product={p} onBuy={buy} buying={buying} />
          ))}
          {shopTab === 'coins' && coinProducts.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic', padding: '8px 0' }}>
              Coin shop coming soon.
            </div>
          )}
          {shopTab === 'gems' && (
            <>
              {sx && (
                <div style={{ padding: '8px 10px', background: 'var(--bg-inset)', border: '1px solid rgba(0,255,224,0.08)', borderRadius: 5, marginBottom: 4 }}>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>
                    {sx.gems_per_batch}💎 → {sx.shards_per_batch}✦ · {sx.remaining_today}/{sx.max_per_day} left today
                  </div>
                  <button
                    onClick={doExchange} disabled={exchanging || sx.remaining_today <= 0}
                    style={{ width: '100%', padding: '5px', fontSize: 10, fontWeight: 700, border: '1px solid rgba(155,48,255,0.3)', borderRadius: 3, background: 'rgba(155,48,255,0.1)', color: 'var(--void-purple)', cursor: 'pointer' }}
                  >
                    {exchanging ? '…' : `Trade ${sx.gems_per_batch}💎 → ${sx.shards_per_batch}✦`}
                  </button>
                </div>
              )}
              {gemProducts.map((p) => <ShopItem key={p.sku} product={p} onBuy={buy} buying={buying} />)}
            </>
          )}
          {shopTab === 'qol' && qolProducts.map((p) => (
            <ShopItem key={p.sku} product={p} onBuy={buy} buying={buying} />
          ))}
        </div>

        <div style={{ height: 1, background: 'rgba(0,255,224,0.05)' }} />

        {/* Live event log */}
        <div className="label-caps">System Log</div>
        <div ref={logRef} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {logEntries.map((e, i) => (
            <div key={i} style={{
              fontSize: 9, padding: '4px 6px',
              borderLeft: `2px solid ${i === 0 ? e.color : 'rgba(255,255,255,0.04)'}`,
              color: i === 0 ? 'rgba(200,220,255,0.6)' : 'var(--muted)',
              fontFamily: 'Consolas, monospace',
              lineHeight: 1.5,
              transition: 'border-color 4s, color 4s',
            }}>
              <span style={{ color: e.color, marginRight: 6 }}>{e.tag}</span>
              {e.msg}
            </div>
          ))}
        </div>

      </div>
    </div>
  )
}

function ShopItem({ product, onBuy, buying }: { product: { sku: string; title: string; description: string; price_cents: number }; onBuy: (sku: string) => void; buying: string | null }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
      background: 'var(--bg-inset)', border: '1px solid rgba(0,255,224,0.06)',
      borderRadius: 5, cursor: 'pointer', transition: 'border-color 0.15s',
    }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(0,255,224,0.2)' }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(0,255,224,0.06)' }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {product.title}
        </div>
        <div style={{ fontSize: 9, color: 'var(--muted)' }}>{product.description}</div>
      </div>
      <button
        onClick={() => onBuy(product.sku)}
        disabled={buying === product.sku}
        style={{
          flexShrink: 0, padding: '3px 7px', fontSize: 10, fontWeight: 700,
          border: 'none', borderRadius: 3,
          background: 'var(--accent)', color: '#000', cursor: 'pointer',
        }}
      >
        {buying === product.sku ? '…' : product.price_cents === 0 ? 'Free' : `$${(product.price_cents / 100).toFixed(2)}`}
      </button>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export function MeRoute() {
  const [zone, setZone] = useState<Zone>('ops')
  const { data: daily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily, staleTime: 30_000 })

  const claimableBadge = (daily ?? []).filter((q) => q.status === 'COMPLETE').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <RootlordSidebar />

        {/* Center */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Sector tabs */}
          <div style={{
            display: 'flex',
            background: 'rgba(4,6,12,0.8)',
            borderBottom: '1px solid rgba(0,255,224,0.06)',
            flexShrink: 0,
            overflowX: 'auto',
          }}>
            {ZONES.map(({ id, icon, label }) => {
              const badge = id === 'ops' && claimableBadge > 0 ? claimableBadge : null
              return (
                <button
                  key={id}
                  onClick={() => setZone(id)}
                  style={{
                    padding: '0 20px',
                    height: 40,
                    display: 'flex', alignItems: 'center', gap: 7,
                    fontSize: 10, fontWeight: 800,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    color: zone === id ? 'var(--accent)' : 'var(--muted)',
                    borderBottom: `2px solid ${zone === id ? 'var(--accent)' : 'transparent'}`,
                    background: zone === id ? 'rgba(0,255,224,0.03)' : 'transparent',
                    border: 'none',
                    borderBottomWidth: 2,
                    borderBottomStyle: 'solid',
                    borderBottomColor: zone === id ? 'var(--accent)' : 'transparent',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    textShadow: zone === id ? '0 0 8px rgba(0,255,224,0.5)' : 'none',
                    transition: 'color 0.15s',
                    position: 'relative',
                  }}
                >
                  {icon} {label}
                  {badge !== null && (
                    <span style={{
                      background: 'var(--magenta)', color: '#fff',
                      fontSize: 8, fontWeight: 900, padding: '1px 4px',
                      borderRadius: 2, marginLeft: 2,
                    }}>{badge}</span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Content area */}
          <div style={{ flex: 1, overflow: 'hidden', padding: 16 }}>
            {zone === 'ops'    && <OpsPanel />}
            {zone === 'combat' && <CombatPanel />}
            {zone === 'summon' && <SummonPanel />}
            {zone === 'story'  && <StubPanel label="📖 Story" path="/app/story" />}
            {zone === 'guild'  && <StubPanel label="🛡️ Guild" path="/app/guild" />}
            {zone === 'raid'   && <StubPanel label="🐉 Raids" path="/app/raids" />}
          </div>
        </div>

        <RightPanel />
      </div>
    </div>
  )
}
```

- [ ] **Step 4.2: Start dev server and load `/app/me`**

```bash
npm --prefix C:/Users/User/.claude/mmorpg/hero-proto/frontend run dev
```

Verify: three-column layout renders; Rootlord art appears; zone tabs switch content; TopBar shows currencies and clock; no TypeScript errors in console.

- [ ] **Step 4.3: Commit**

```bash
git add frontend/src/routes/Me.tsx
git commit -m "feat: full lobby rewrite — three-column zone-tab layout with Rootlord"
```

---

## Task 5: Rewrite Shop.tsx — Three-Tab Shop

**Files:**
- Modify: `frontend/src/routes/Shop.tsx`

- [ ] **Step 5.1: Replace Shop.tsx**

```tsx
// frontend/src/routes/Shop.tsx
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchShop, buyProduct, exchangeShards } from '../api/shop'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

type ShopTab = 'coins' | 'gems' | 'qol'

const TAB_META: { id: ShopTab; icon: string; label: string; kinds: string[] }[] = [
  { id: 'coins', icon: '🪙', label: 'Coin Shop',  kinds: ['COIN_PACK'] },
  { id: 'gems',  icon: '💎', label: 'Gem Shop',   kinds: ['GEM_PACK', 'STARTER_BUNDLE', 'SHARD_PACK', 'ACCESS_CARD_PACK'] },
  { id: 'qol',   icon: '⚙️', label: 'QoL Shop',   kinds: ['WEEKLY_BUNDLE', 'SEASONAL_BUNDLE'] },
]

export function ShopRoute() {
  const qc = useQueryClient()
  const { data: shop, isLoading } = useQuery({ queryKey: ['shop'], queryFn: fetchShop, staleTime: 2 * 60_000 })
  const [tab, setTab] = useState<ShopTab>('coins')
  const [buying, setBuying] = useState<string | null>(null)
  const [exchanging, setExchanging] = useState(false)

  if (isLoading) return <SkeletonGrid count={8} height={100} />
  if (!shop) return <div className="muted">Shop unavailable.</div>

  async function buy(sku: string) {
    setBuying(sku)
    try {
      const res = await buyProduct(sku)
      const parts = Object.entries(res.granted ?? {}).filter(([, v]) => Number(v) > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Purchased! ${parts.join(', ')}` : 'Purchased!')
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Purchase failed') }
    finally { setBuying(null) }
  }

  async function doExchange() {
    setExchanging(true)
    try {
      const res = await exchangeShards()
      toast.success(`+${res.shards_granted} shards!`)
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Exchange failed') }
    finally { setExchanging(false) }
  }

  const meta = TAB_META.find((t) => t.id === tab)!
  const products = tab === 'qol'
    ? shop.products.filter((p) => !['GEM_PACK','COIN_PACK','STARTER_BUNDLE','SHARD_PACK','ACCESS_CARD_PACK'].includes(p.kind))
    : shop.products.filter((p) => meta.kinds.includes(p.kind))

  const sx = shop.shard_exchange

  return (
    <div className="stack">
      {/* Tab selector */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {TAB_META.map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              padding: '16px 12px', borderRadius: 8, cursor: 'pointer',
              border: `1px solid ${tab === id ? 'rgba(0,255,224,0.4)' : 'var(--border)'}`,
              background: tab === id ? 'rgba(0,255,224,0.06)' : 'var(--panel)',
              color: tab === id ? 'var(--accent)' : 'var(--muted)',
              textAlign: 'center', transition: 'all 0.15s',
              boxShadow: tab === id ? '0 0 20px rgba(0,255,224,0.08)' : 'none',
            }}
          >
            <div style={{ fontSize: 28, marginBottom: 6 }}>{icon}</div>
            <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</div>
          </button>
        ))}
      </div>

      {/* Gem-tab: shard exchange first */}
      {tab === 'gems' && sx && (
        <div className="card" style={{ borderColor: 'rgba(155,48,255,0.3)' }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>💎→✦ Shard Exchange</div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
            {sx.gems_per_batch}💎 → {sx.shards_per_batch}✦ · {sx.remaining_today}/{sx.max_per_day} trades left today
          </div>
          <button className="primary" onClick={doExchange} disabled={exchanging || sx.remaining_today <= 0}>
            {exchanging ? '…' : `Trade ${sx.gems_per_batch}💎 for ${sx.shards_per_batch}✦`}
          </button>
        </div>
      )}

      {/* Starter bundle */}
      {tab === 'gems' && shop.starter && (
        <div className="card" style={{ border: '1px solid var(--r-legendary)', background: 'rgba(255,215,0,0.04)' }}>
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

      {/* Products grid */}
      {products.length === 0 && (
        <div className="card muted" style={{ textAlign: 'center', padding: 32 }}>
          Nothing in this shop yet — check back soon.
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {products.map((p) => (
          <div key={p.sku} className="card" style={{ borderColor: p.kind === 'COIN_PACK' ? 'rgba(255,215,0,0.2)' : 'var(--border)' }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{p.title}</div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{p.description}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: p.price_cents === 0 ? 'var(--good)' : 'var(--warn)', fontWeight: 700 }}>
                {p.price_cents === 0 ? 'Free' : `$${(p.price_cents / 100).toFixed(2)}`}
              </span>
              <button className="primary" style={{ fontSize: 12 }} onClick={() => buy(p.sku)} disabled={!!buying}>
                {buying === p.sku ? '…' : 'Buy'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Purchase history */}
      {shop.history.length > 0 && (
        <div className="card">
          <div style={{ fontWeight: 700, marginBottom: 10 }}>Recent Purchases</div>
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

- [ ] **Step 5.2: Verify `/app/shop` renders with three tabs**

Navigate to `/app/shop`. Gems tab should show existing gem products. Coins tab should show empty state (until backend step). QoL tab should show existing QoL products.

- [ ] **Step 5.3: Commit**

```bash
git add frontend/src/routes/Shop.tsx
git commit -m "feat: three-tab shop — Coins / Gems / QoL"
```

---

## Task 6: Backend — Add COIN_PACK Kind and Coin Products

**Files:**
- Modify: `app/models.py` — add `COIN_PACK` to `ShopProductKind`
- Modify: `app/seed.py` — add coin product SKUs

No migration needed: `ShopProductKind` is stored as `String(32)`, not a DB enum.

- [ ] **Step 6.1: Add COIN_PACK to ShopProductKind in models.py**

Find the `ShopProductKind` class (line ~149) and add `COIN_PACK`:

```python
class ShopProductKind(StrEnum):
    GEM_PACK = "GEM_PACK"
    COIN_PACK = "COIN_PACK"          # ← add this line
    SHARD_PACK = "SHARD_PACK"
    ACCESS_CARD_PACK = "ACCESS_CARD_PACK"
    STARTER_BUNDLE = "STARTER_BUNDLE"
    WEEKLY_BUNDLE = "WEEKLY_BUNDLE"
    SEASONAL_BUNDLE = "SEASONAL_BUNDLE"
```

- [ ] **Step 6.2: Add coin products to seed.py**

Find the `SHOP_PRODUCTS` list (or the equivalent seeding block, around line 1031) and add the coin products after the gem packs:

```python
# ── Coin Shop ────────────────────────────────────────────────────────────────
{
    "sku": "coin_sack_daily",
    "title": "Coin Sack",
    "description": "5,000 coins. Free once per day.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 0, "sort_order": 50,
    "per_account_limit": 0,  # 0 = no lifetime limit; daily enforced by kind
    "contents": {"coins": 5000},
},
{
    "sku": "coin_chest",
    "title": "Coin Chest",
    "description": "25,000 coins. Classic IT salary move.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 0, "sort_order": 51,
    "per_account_limit": 0,
    "contents": {"coins": 25000, "gems": -50},  # costs 50 gems via mock-pay
},
{
    "sku": "coin_vault",
    "title": "Coin Vault",
    "description": "100,000 coins. Senior dev territory.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 0, "sort_order": 52,
    "per_account_limit": 0,
    "contents": {"coins": 100000, "gems": -180},
},
{
    "sku": "devs_stash",
    "title": "Dev's Stash",
    "description": "500,000 coins. The Rootlord's personal reserve.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 499, "sort_order": 53,
    "per_account_limit": 0,
    "contents": {"coins": 500000},
},
```

> **Note:** The `coin_chest` and `coin_vault` use `price_cents: 0` with gem costs in `contents`. The mock-payment path doesn't deduct gems from `contents` — it just grants them. For gem-cost purchases, the frontend should call a separate deduct-gems endpoint or use the existing `buyProduct` with a `gems` SKU pattern. For now, add them as paid (`price_cents > 0`) until a gem-deduct flow exists:

Revised coin products with real prices for now (gem deduction in a future sprint):

```python
{
    "sku": "coin_sack_daily",
    "title": "Coin Sack",
    "description": "5,000 coins. Free once per day.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 0, "sort_order": 50,
    "per_account_limit": 1,
    "contents": {"coins": 5000},
},
{
    "sku": "coin_chest",
    "title": "Coin Chest",
    "description": "25,000 coins. Classic IT salary move.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 99, "sort_order": 51,
    "per_account_limit": 0,
    "contents": {"coins": 25000},
},
{
    "sku": "coin_vault",
    "title": "Coin Vault",
    "description": "100,000 coins. Senior dev territory.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 199, "sort_order": 52,
    "per_account_limit": 0,
    "contents": {"coins": 100000},
},
{
    "sku": "devs_stash",
    "title": "Dev's Stash",
    "description": "500,000 coins. The Rootlord's personal reserve.",
    "kind": ShopProductKind.COIN_PACK, "price_cents": 499, "sort_order": 53,
    "per_account_limit": 0,
    "contents": {"coins": 500000},
},
```

- [ ] **Step 6.3: Run seed to insert new products**

```bash
cd C:/Users/User/.claude/mmorpg/hero-proto
uv run python -c "from app.seed import seed; seed()"
```

Expected: no errors; "seeded N shop products" log line.

- [ ] **Step 6.4: Verify products appear in API**

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1/shop/products | python -m json.tool | grep -A3 "COIN_PACK"
```

Expected: four coin products with kind `COIN_PACK`.

- [ ] **Step 6.5: Commit**

```bash
git add app/models.py app/seed.py
git commit -m "feat: COIN_PACK shop kind + coin product SKUs (sack/chest/vault/stash)"
```

---

## Task 7: End-to-End Smoke Test

- [ ] **Step 7.1: Run full test suite**

```bash
cd C:/Users/User/.claude/mmorpg/hero-proto
uv run pytest -x -q
```

Expected: all tests pass (630 passed, 2 skipped). No new failures from models.py change.

- [ ] **Step 7.2: Manual smoke test — lobby**

Start dev server + backend:
```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Check:
1. `/app/me` — full-viewport three-column layout, no NavBar
2. Rootlord art loads; quote rotates every 6 seconds
3. Zone tabs: Ops / Combat / Summon / Story / Guild / Raid all switch correctly
4. Right panel shop: Coins tab shows 4 products, Gems tab shows existing products + shard exchange, QoL tab shows QoL products
5. Claim daily quest button works
6. `/app/roster`, `/app/arena` — NavBar still visible, layout unchanged

- [ ] **Step 7.3: Final commit**

```bash
git add -A
git commit -m "chore: lobby overhaul complete — dark cyberpunk UI, Rootlord mascot, three-tab shop"
```
