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

  const visibleTabs = NAV_TABS

  const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
    background: 'transparent',
    color: isActive ? 'var(--text)' : 'var(--muted)',
    padding: '6px 12px',
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
