import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../../store/auth'
import { useMe } from '../../hooks/useMe'
import { apiFetch } from '../../api/client'
import { fetchDaily } from '../../api/daily'
import { fetchDmThreads } from '../../api/friends'
import { fetchBattlePass } from '../../api/battlePass'
import { claimableTierCount } from '../../routes/BattlePass'
import { BellButton } from './BellPopover'
import { SoundButton } from './SoundPopover'

type Tab = { path: string; label: string }

const MANAGE_TABS: Tab[] = [
  { path: '/app/inventory',    label: 'Inventory' },
  { path: '/app/shards',       label: 'Shards' },
  { path: '/app/crafting',     label: 'Crafting' },
  { path: '/app/daily',        label: 'Daily' },
  { path: '/app/battle-pass',  label: 'Battle Pass' },
  { path: '/app/shop',         label: 'Shop' },
  { path: '/app/guild',        label: 'Guild' },
  { path: '/app/friends',      label: 'Friends' },
  { path: '/app/collections',  label: 'Collections' },
  { path: '/app/achievements', label: 'Achievements' },
  { path: '/app/account',      label: 'Account' },
]

function fmtBig(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return String(n)
}

export function TopNav() {
  const jwt = useAuthStore((s) => s.jwt)
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const { data: me } = useMe()
  const [stripRef, setStripRef] = useState<HTMLElement | null>(null)

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
  const { data: dmThreads } = useQuery({
    queryKey: ['dm-threads'],
    queryFn: fetchDmThreads,
    refetchInterval: 30_000,
    enabled: !!jwt,
    retry: false,
  })
  const { data: bpData } = useQuery({
    queryKey: ['battle-pass'],
    queryFn: fetchBattlePass,
    refetchInterval: 60_000,
    enabled: !!jwt,
    retry: false,
  })

  const dailyClaimable = (dailyData ?? []).filter((q) => q.status === 'COMPLETE').length
  const dmUnread = (dmThreads ?? []).reduce((sum, t) => sum + (t.unread ?? 0), 0)
  const bpClaimable = claimableTierCount(bpData)

  function badgeFor(path: string): number | null {
    if (path === '/app/daily' && dailyClaimable > 0) return dailyClaimable
    if (path === '/app/friends' && dmUnread > 0) return dmUnread
    if (path === '/app/battle-pass' && bpClaimable > 0) return bpClaimable
    return null
  }

  // Auto-scroll active tab into view
  useEffect(() => {
    if (!stripRef) return
    const active = stripRef.querySelector<HTMLAnchorElement>('.topnav-tab.is-active')
    active?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
  }, [location.pathname, stripRef])

  return (
    <header className="topnav">
      <div className="topnav-bar">
        <button type="button" className="topnav-brand" onClick={() => navigate('/app/lobby')}>
          [ HERO-PROTO ]
        </button>
        {me && (
          <div className="topnav-curr" aria-label="currency">
            <span className="c"><span className="dot c"></span>{me.energy}</span>
            <span className="c"><span className="dot p"></span>{fmtBig(me.gems)}</span>
            <span className="c"><span className="dot g"></span>{fmtBig(me.coins)}</span>
          </div>
        )}
        <div className="topnav-actions">
          <BellButton />
          <SoundButton />
          <button onClick={logout} className="icon-btn" aria-label="Sign out" title="Sign out" style={{ fontSize: 13 }}>
            ⏻
          </button>
        </div>
      </div>

      <nav className="topnav-strip" aria-label="Manage" ref={setStripRef}>
        {MANAGE_TABS.map((t) => {
          const badge = badgeFor(t.path)
          return (
            <NavLink
              key={t.path}
              to={t.path}
              className={({ isActive }) => 'topnav-tab' + (isActive ? ' is-active' : '')}
            >
              {t.label}
              {badge !== null && <span className="topnav-tab-badge">{badge > 99 ? '99+' : badge}</span>}
            </NavLink>
          )
        })}
        {!!eventData && (
          <NavLink
            to="/app/event"
            className={({ isActive }) => 'topnav-tab topnav-event' + (isActive ? ' is-active' : '')}
          >
            ⚡ Event
          </NavLink>
        )}
      </nav>
    </header>
  )
}
