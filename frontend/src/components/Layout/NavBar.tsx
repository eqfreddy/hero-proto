import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../../store/auth'
import { apiFetch } from '../../api/client'
import { fetchDaily } from '../../api/daily'
import { fetchDmThreads } from '../../api/friends'
import { fetchBattlePass } from '../../api/battlePass'
import { claimableTierCount } from '../../routes/BattlePass'
import { BellButton } from './BellPopover'
import { SoundButton } from './SoundPopover'

type Tab = { path: string; label: string; icon: string }

const NAV_GROUPS: { label: string; tabs: Tab[] }[] = [
  { label: '', tabs: [
    { path: '/app/me', label: 'Home', icon: '🏠' },
  ]},
  { label: 'Heroes', tabs: [
    { path: '/app/roster',    label: 'Roster',    icon: '🦸' },
    { path: '/app/summon',    label: 'Summon',    icon: '🌀' },
    { path: '/app/inventory', label: 'Inventory', icon: '📦' },
    { path: '/app/shards',    label: 'Shards',    icon: '💎' },
    { path: '/app/crafting',  label: 'Crafting',  icon: '🔨' },
  ]},
  { label: 'Combat', tabs: [
    { path: '/app/stages', label: 'Stages', icon: '⚔️' },
    { path: '/app/story',  label: 'Story',  icon: '📖' },
    { path: '/app/arena',  label: 'Arena',  icon: '🏟️' },
    { path: '/app/tower',  label: 'Tower',  icon: '🗼' },
    { path: '/app/raids',  label: 'Raids',  icon: '🐉' },
  ]},
  { label: 'Social', tabs: [
    { path: '/app/daily',       label: 'Daily',       icon: '📋' },
    { path: '/app/battle-pass', label: 'Battle Pass', icon: '🎫' },
    { path: '/app/shop',        label: 'Shop',        icon: '🛒' },
    { path: '/app/guild',       label: 'Guild',       icon: '🛡️' },
    { path: '/app/friends',     label: 'Friends',     icon: '🤝' },
  ]},
  { label: 'Collect', tabs: [
    { path: '/app/collections', label: 'Collections', icon: '📜' },
  ]},
  { label: 'You', tabs: [
    { path: '/app/achievements', label: 'Achievements', icon: '🏆' },
    { path: '/app/account',      label: 'Account',      icon: '⚙️' },
  ]},
]

export function NavBar() {
  const jwt = useAuthStore((s) => s.jwt)
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Close drawer on route change
  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  // Lock body scroll when drawer is open
  useEffect(() => {
    document.body.style.overflow = drawerOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [drawerOpen])

  function logout() {
    clearJwt()
    qc.clear()
    window.location.href = '/'
  }

  const { data: eventData } = useQuery({
    queryKey: ['active-event'],
    queryFn: () => apiFetch<unknown>('/events/active'),
    refetchInterval: 60_000,
    enabled: !!jwt,
    retry: false,
  })

  const { data: dailyData } = useQuery({
    queryKey: ['daily'],
    queryFn: fetchDaily,
    refetchInterval: 60_000,
    enabled: !!jwt,
    retry: false,
  })
  const dailyClaimable = (dailyData ?? []).filter((q) => q.status === 'COMPLETE').length

  const { data: dmThreads } = useQuery({
    queryKey: ['dm-threads'],
    queryFn: fetchDmThreads,
    refetchInterval: 30_000,
    enabled: !!jwt,
    retry: false,
  })
  const dmUnread = (dmThreads ?? []).reduce((sum, t) => sum + (t.unread ?? 0), 0)

  const { data: bpData } = useQuery({
    queryKey: ['battle-pass'],
    queryFn: fetchBattlePass,
    refetchInterval: 60_000,
    enabled: !!jwt,
    retry: false,
  })
  const bpClaimable = claimableTierCount(bpData)

  if (!jwt) return null

  function badgeFor(path: string) {
    if (path === '/app/daily' && dailyClaimable > 0) return dailyClaimable
    if (path === '/app/friends' && dmUnread > 0) return dmUnread
    if (path === '/app/battle-pass' && bpClaimable > 0) return bpClaimable
    return null
  }

  const allGroups = eventData
    ? [...NAV_GROUPS, { label: 'Event', tabs: [{ path: '/app/event', label: 'Event', icon: '⚡' }] }]
    : NAV_GROUPS

  return (
    <>
      <header style={{
        background: 'var(--panel)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, zIndex: 50,
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}>
        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 18px' }}>
          <button onClick={() => navigate('/app/me')} className="brand-btn" aria-label="hero-proto home">
            <span className="brand-mark">H</span>
            <span className="brand-text">hero-proto</span>
          </button>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <BellButton />
            <SoundButton />
            {/* Hamburger — mobile only */}
            <button
              className="icon-btn nav-hamburger"
              aria-label="Open menu"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
              style={{ fontSize: 18 }}
            >
              ☰
            </button>
            <button onClick={logout} className="icon-btn" aria-label="Sign out" title="Sign out" style={{ fontSize: 13 }}>
              ⏻
            </button>
          </div>
        </div>

        {/* Tab strip — desktop only */}
        <nav className="nav-strip" aria-label="Primary">
          {NAV_GROUPS.map(({ tabs }, gi) => (
            <span key={gi} style={{ display: 'contents' }}>
              {gi > 0 && <span className="nav-divider" aria-hidden="true" />}
              {tabs.map((t) => {
                const badge = badgeFor(t.path)
                return (
                  <NavLink key={t.path} to={t.path} className={({ isActive }) => 'nav-tab' + (isActive ? ' is-active' : '')}>
                    <span className="nav-tab-icon" aria-hidden="true">{t.icon}</span>
                    <span>{t.label}</span>
                    {badge !== null && (
                      <span className="nav-tab-badge">{badge > 99 ? '99+' : badge}</span>
                    )}
                  </NavLink>
                )
              })}
            </span>
          ))}
          {!!eventData && (
            <NavLink to="/app/event" className={({ isActive }) => 'nav-tab' + (isActive ? ' is-active' : '')} style={{ color: 'var(--warn)' }}>
              <span className="nav-tab-icon" aria-hidden="true">⚡</span>
              <span>Event</span>
              <span className="nav-tab-dot" aria-hidden="true" style={{ background: 'var(--warn)' }} />
            </NavLink>
          )}
        </nav>
      </header>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="nav-drawer-backdrop" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      )}
      <div className={`nav-drawer${drawerOpen ? ' nav-drawer--open' : ''}`} role="dialog" aria-label="Navigation menu" aria-modal="true">
        <div className="nav-drawer-handle" />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 20px 16px' }}>
          <span style={{ fontWeight: 800, fontSize: 16 }}>Menu</span>
          <button className="icon-btn" onClick={() => setDrawerOpen(false)} aria-label="Close menu" style={{ fontSize: 18 }}>✕</button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, padding: '0 16px 40px' }}>
          {allGroups.map(({ label, tabs }) => (
            <div key={label} style={{ marginBottom: 20 }}>
              {label && (
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: 'var(--muted)', padding: '0 4px 8px', textTransform: 'uppercase' }}>
                  {label}
                </div>
              )}
              <div className="nav-drawer-grid">
                {tabs.map((t) => {
                  const badge = badgeFor(t.path)
                  return (
                    <NavLink
                      key={t.path}
                      to={t.path}
                      className={({ isActive }) => 'nav-drawer-item' + (isActive ? ' is-active' : '')}
                    >
                      <span style={{ fontSize: 22 }}>{t.icon}</span>
                      <span style={{ fontSize: 12, fontWeight: 600 }}>{t.label}</span>
                      {badge !== null && (
                        <span className="nav-tab-badge" style={{ position: 'absolute', top: 6, right: 6 }}>
                          {badge > 99 ? '99+' : badge}
                        </span>
                      )}
                    </NavLink>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
