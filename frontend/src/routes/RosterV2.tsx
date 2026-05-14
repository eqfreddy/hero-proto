import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import type { Hero } from '../types'
import './Lobby.css'
import './RosterV2.css'

type FilterKey = 'ALL' | 'RESISTANCE' | 'CORP_GREED' | 'EXILE' | 'NEUTRAL' | 'EPIC_PLUS'
type SortKey = 'POWER' | 'LEVEL' | 'RARITY' | 'RECENT'

const RARITY_TIER: Record<string, string> = {
  COMMON: 'FLOPPY',
  UNCOMMON: 'HARD-DISK',
  RARE: 'SSD',
  EPIC: 'RAID-0',
  LEGENDARY: 'RAID-5',
  MYTH: 'LEGEN-WAIT-DARY',
}

const SORT_LABELS: Record<SortKey, string> = {
  POWER: 'POWER ▼',
  LEVEL: 'LEVEL ▼',
  RARITY: 'RARITY ▼',
  RECENT: 'RECENT ▼',
}

const NEXT_SORT: Record<SortKey, SortKey> = {
  POWER: 'LEVEL',
  LEVEL: 'RARITY',
  RARITY: 'RECENT',
  RECENT: 'POWER',
}

export function RosterV2Route() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const [filter, setFilter] = useState<FilterKey>('ALL')
  const [sort, setSort] = useState<SortKey>('POWER')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const playerFaction = me?.faction ?? 'EXILE'

  const factionCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: 0, RESISTANCE: 0, CORP_GREED: 0, EXILE: 0, NEUTRAL: 0, EPIC_PLUS: 0 }
    if (!heroes) return counts
    for (const h of heroes) {
      counts.ALL++
      const f = (h.template.faction ?? 'NEUTRAL') as string
      if (counts[f] != null) counts[f]++
      if (['EPIC', 'LEGENDARY', 'MYTH'].includes(h.template.rarity)) counts.EPIC_PLUS++
    }
    return counts
  }, [heroes])

  const filtered = useMemo(() => {
    if (!heroes) return []
    let list: Hero[] = heroes
    if (filter === 'EPIC_PLUS') {
      list = list.filter((h) => ['EPIC', 'LEGENDARY', 'MYTH'].includes(h.template.rarity))
    } else if (filter !== 'ALL') {
      list = list.filter((h) => (h.template.faction ?? 'NEUTRAL') === filter)
    }
    const rarityOrder = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']
    list = [...list].sort((a, b) => {
      switch (sort) {
        case 'POWER': return b.power - a.power
        case 'LEVEL': return b.level - a.level
        case 'RARITY':
          return rarityOrder.indexOf(b.template.rarity) - rarityOrder.indexOf(a.template.rarity)
        case 'RECENT': return b.id - a.id
      }
    })
    return list
  }, [heroes, filter, sort])

  const selected = filtered.find((h) => h.id === selectedId) ?? null

  const factionChips: Array<{ key: FilterKey; label: string; data?: string }> = [
    { key: 'ALL', label: 'ALL' },
    { key: 'RESISTANCE', label: 'RES', data: 'RESISTANCE' },
    { key: 'CORP_GREED', label: 'CORP', data: 'CORP_GREED' },
    { key: 'EXILE', label: 'EXILE', data: 'EXILE' },
    { key: 'EPIC_PLUS', label: 'EPIC+' },
  ]

  if (!heroes) {
    return (
      <div className="lobby-root" data-faction={playerFaction}>
        <div className="ros-hdr"><span className="title">ROSTER · loading…</span></div>
      </div>
    )
  }

  return (
    <div className="lobby-root" data-faction={playerFaction}>
      <div className="ros-hdr">
        <span className="title">ROSTER · <b>{heroes.length}</b> HEROES</span>
        <button type="button" className="search" aria-label="search">⌕</button>
      </div>

      <div className="ros-chips">
        {factionChips.map((c) => (
          <button
            key={c.key}
            type="button"
            className={`chip${filter === c.key ? ' on' : ''}`}
            data-f={c.data}
            onClick={() => setFilter(c.key)}
          >
            {c.label} · {factionCounts[c.key] ?? 0}
          </button>
        ))}
      </div>

      <div className="ros-sort">
        <span>// sorted by</span>
        <button type="button" className="right" onClick={() => setSort(NEXT_SORT[sort])}>
          {SORT_LABELS[sort]}
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="ros-empty">
          NO HEROES MATCH FILTER
          <br />
          <a className="link" href="#" onClick={(e) => { e.preventDefault(); setFilter('ALL') }}>SHOW ALL</a>
        </div>
      ) : (
        <div className="ros-grid">
          {filtered.map((h) => {
            const fac = (h.template.faction ?? 'NEUTRAL') as string
            const isSel = h.id === selectedId
            return (
              <div
                key={h.id}
                className={`ros-card${isSel ? ' sel' : ''}`}
                data-fac={fac}
                onClick={() => setSelectedId(isSel ? null : h.id)}
                onDoubleClick={() => navigate(`/app/roster/${h.id}`)}
              >
                <div className="por">
                  <span className="rar">
                    {Array.from({ length: h.stars }).map((_, i) => <i key={i}></i>)}
                  </span>
                  <span className="lv">L{h.level}</span>
                  <div className="fig">
                    <img
                      className="bust"
                      src={`/app/static/heroes/busts/${h.template.code}.png`}
                      alt={h.template.name}
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                    />
                  </div>
                </div>
                <div className="nm">{h.template.name}</div>
                <div className="tier-mini">{RARITY_TIER[h.template.rarity] ?? h.template.rarity}</div>
              </div>
            )
          })}
        </div>
      )}

      {selected && (
        <div className="ros-action" onClick={() => navigate(`/app/roster/${selected.id}`)}>
          <span>SELECT · {selected.template.name}</span>
          <span className="arrow">›</span>
        </div>
      )}

      <nav className="lobby-bnav">
        <button type="button" className="item" onClick={() => navigate('/app/lobby')}>
          <span className="ico">H</span>HOME
        </button>
        <button type="button" className="item on">
          <span className="ico">R</span>ROSTER
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/summon-v2')}>
          <span className="ico summon">S</span>SUMMON
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/stages')}>
          <span className="ico">B</span>BATTLE
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/shop')}>
          <span className="ico">$</span>SHOP
        </button>
      </nav>
    </div>
  )
}

export default RosterV2Route
