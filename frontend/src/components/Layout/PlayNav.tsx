import { NavLink, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTemplateShards, SHARDS_TO_ASCEND_FROM, SHARDS_TO_SKILL_UP } from '../../api/heroes'
import { useHeroes } from '../../hooks/useHeroes'

type Slot = { path: string; label: string; ico: string; match: (p: string) => boolean }

// Five fat tabs. Each one is a hub: tapping it lands on a primary route,
// from which secondary routes (sub-tabs / inline links) are reachable.
//
//  Home    →  me                                  (the main hub)
//  Heroes  →  roster   + summon, shards, inventory, crafting
//  Battle  →  stages   + arena, raids, tower
//  Shop    →  shop     + battle pass
//  Social  →  guild    + friends, account, collections, achievements,
//                        daily, story, quests
const SLOTS: Slot[] = [
  {
    path: '/app/me', label: 'Home', ico: 'H',
    match: (p) => p === '/' || p === '/app' || p === '/app/' || p === '/app/me',
  },
  {
    path: '/app/roster', label: 'Heroes', ico: 'R',
    match: (p) =>
      p.startsWith('/app/roster') ||
      p.startsWith('/app/summon') ||
      p.startsWith('/app/shards') ||
      p.startsWith('/app/inventory') ||
      p.startsWith('/app/crafting'),
  },
  {
    path: '/app/stages', label: 'Battle', ico: 'B',
    match: (p) =>
      p.startsWith('/app/stages') ||
      p.startsWith('/app/arena') ||
      p.startsWith('/app/raids') ||
      p.startsWith('/app/tower') ||
      p === '/app/battle' ||
      p.startsWith('/app/battle/') ||
      p.startsWith('/app/battle-v2') ||
      p.startsWith('/battle'),
  },
  {
    path: '/app/shop', label: 'Shop', ico: 'S',
    match: (p) => p.startsWith('/app/shop') || p.startsWith('/app/battle-pass'),
  },
  {
    path: '/app/guild', label: 'Social', ico: '★',
    match: (p) =>
      p.startsWith('/app/guild') ||
      p.startsWith('/app/friends') ||
      p.startsWith('/app/account') ||
      p.startsWith('/app/collections') ||
      p.startsWith('/app/achievements') ||
      p.startsWith('/app/daily') ||
      p.startsWith('/app/story') ||
      p.startsWith('/app/quests'),
  },
]

export function PlayNav() {
  const location = useLocation()
  const { data: heroes } = useHeroes()
  const { data: templateShards } = useQuery({ queryKey: ['template-shards'], queryFn: fetchTemplateShards })
  const heroUpgradeCount = (heroes ?? []).filter((h) => {
    const balance = templateShards?.[h.template.code] ?? 0
    const ascendCost = h.stars < 6 ? (SHARDS_TO_ASCEND_FROM[h.stars] ?? null) : null
    const skillCost = SHARDS_TO_SKILL_UP[h.special_level] ?? null
    return (ascendCost != null && balance >= ascendCost) || (skillCost != null && balance >= skillCost)
  }).length

  return (
    <nav className="playnav" aria-label="Play">
      {SLOTS.map((s) => {
        const active = s.match(location.pathname)
        const showHeroMarker = s.label === 'Heroes' && heroUpgradeCount > 0
        return (
          <NavLink
            key={s.path}
            to={s.path}
            className={'playnav-item' + (active ? ' is-active' : '') + (showHeroMarker ? ' has-upgrade' : '')}
          >
            <span className="ico" aria-hidden="true">
              {s.ico}
              {showHeroMarker && <span className="playnav-dot">{heroUpgradeCount > 9 ? '9+' : heroUpgradeCount}</span>}
            </span>
            <span>{s.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}
