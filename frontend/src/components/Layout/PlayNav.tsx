import { NavLink, useLocation } from 'react-router-dom'

type Slot = { path: string; label: string; ico: string; match?: (p: string) => boolean; modifier?: string }

const SLOTS: Slot[] = [
  { path: '/app/lobby',  label: 'Home',   ico: 'H', match: (p) => p === '/app/lobby' || p === '/app' || p === '/' },
  { path: '/app/roster', label: 'Roster', ico: 'R', match: (p) => p.startsWith('/app/roster') },
  { path: '/app/summon', label: 'Summon', ico: 'S', match: (p) => p.startsWith('/app/summon'), modifier: 'is-summon' },
  { path: '/app/battle', label: 'Battle', ico: 'B', match: (p) =>
      p === '/app/battle' || p.startsWith('/app/battle/') || p.startsWith('/app/battle-v2') ||
      p.startsWith('/app/stages') || p.startsWith('/app/arena') || p.startsWith('/app/tower') || p.startsWith('/app/raids') ||
      p.startsWith('/battle')
  },
  { path: '/app/story',  label: 'Story',  ico: 'T', match: (p) => p.startsWith('/app/story') },
]

export function PlayNav() {
  const location = useLocation()
  return (
    <nav className="playnav" aria-label="Play">
      {SLOTS.map((s) => {
        const active = s.match ? s.match(location.pathname) : location.pathname === s.path
        return (
          <NavLink
            key={s.path}
            to={s.path}
            className={'playnav-item' + (s.modifier ? ' ' + s.modifier : '') + (active ? ' is-active' : '')}
          >
            <span className="ico" aria-hidden="true">{s.ico}</span>
            <span>{s.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}
