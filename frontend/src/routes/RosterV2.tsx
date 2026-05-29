import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { fetchTemplateShards, SHARDS_TO_ASCEND_FROM, SHARDS_TO_SKILL_UP } from '../api/heroes'
import type { Hero } from '../types'
import './Lobby.css'
import './RosterV2.css'
import { HeroPortrait } from '../components/HeroPortrait'

type FilterKey = 'ALL' | 'EPIC_PLUS' | string
type SortKey = 'POWER' | 'LEVEL' | 'RARITY' | 'RECENT'

const RARITY_TIER: Record<string, string> = {
  COMMON: 'FLOPPY',
  UNCOMMON: 'HARD-DISK',
  RARE: 'SSD',
  EPIC: 'RAID-0',
  LEGENDARY: 'RAID-5',
  MYTH: 'MYTH',
}

const SORT_LABELS: Record<SortKey, string> = {
  POWER: 'POWER v',
  LEVEL: 'LEVEL v',
  RARITY: 'RARITY v',
  RECENT: 'RECENT v',
}

const NEXT_SORT: Record<SortKey, SortKey> = {
  POWER: 'LEVEL',
  LEVEL: 'RARITY',
  RARITY: 'RECENT',
  RECENT: 'POWER',
}

function shortFactionLabel(f: string): string {
  const map: Record<string, string> = {
    RESISTANCE: 'RES',
    CORP_GREED: 'CORP',
    EXILE: 'EXILE',
    NEUTRAL: 'NEUT',
    LEGACY: 'LEG',
    HELPDESK: 'HELP',
    SHADOW_IT: 'SHADOW',
    GREYHAT: 'GREY',
  }
  return map[f] ?? f.slice(0, 6).toUpperCase()
}

function rarityRank(rarity: string): number {
  return ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH'].indexOf(rarity)
}

function StatLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="ros-focus-stat">
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </div>
  )
}

function upgradeInfo(hero: Hero, shards: Record<string, number> | undefined) {
  const balance = shards?.[hero.template.code] ?? 0
  const ascendCost = hero.stars < 6 ? (SHARDS_TO_ASCEND_FROM[hero.stars] ?? null) : null
  const skillCost = SHARDS_TO_SKILL_UP[hero.special_level] ?? null
  const canAscend = ascendCost != null && balance >= ascendCost
  const canSkill = skillCost != null && balance >= skillCost
  const nextAscend = ascendCost == null ? 'Max stars' : `${balance}/${ascendCost} shards`
  const nextSkill = skillCost == null ? 'Max skill' : `${balance}/${skillCost} skill`
  const cardAscend = ascendCost == null ? 'Max asc' : canAscend ? 'Asc ready' : `${balance}/${ascendCost} asc`
  const cardSkill = skillCost == null ? 'Max skill' : canSkill ? 'Skill ready' : `${balance}/${skillCost} skill`
  return {
    balance,
    ascendCost,
    skillCost,
    canAscend,
    canSkill,
    ready: canAscend || canSkill,
    nextAscend,
    nextSkill,
    cardAscend,
    cardSkill,
  }
}

export function RosterV2Route() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: templateShards } = useQuery({ queryKey: ['template-shards'], queryFn: fetchTemplateShards })
  const [filter, setFilter] = useState<FilterKey>('ALL')
  const [sort, setSort] = useState<SortKey>('POWER')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const playerFaction = me?.faction ?? 'EXILE'

  const factionCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: 0, EPIC_PLUS: 0 }
    if (!heroes) return counts
    for (const h of heroes) {
      counts.ALL += 1
      const faction = (h.template.faction ?? 'NEUTRAL') as string
      counts[faction] = (counts[faction] ?? 0) + 1
      if (['EPIC', 'LEGENDARY', 'MYTH'].includes(h.template.rarity)) counts.EPIC_PLUS += 1
    }
    return counts
  }, [heroes])

  const dynamicFactions = useMemo(() => {
    if (!heroes) return [] as string[]
    const seen = new Set<string>()
    for (const h of heroes) seen.add((h.template.faction ?? 'NEUTRAL') as string)
    return Array.from(seen).sort((a, b) => (factionCounts[b] ?? 0) - (factionCounts[a] ?? 0))
  }, [heroes, factionCounts])

  const filtered = useMemo(() => {
    if (!heroes) return []
    let list: Hero[] = heroes
    if (filter === 'EPIC_PLUS') {
      list = list.filter((h) => ['EPIC', 'LEGENDARY', 'MYTH'].includes(h.template.rarity))
    } else if (filter !== 'ALL') {
      list = list.filter((h) => (h.template.faction ?? 'NEUTRAL') === filter)
    }

    return [...list].sort((a, b) => {
      switch (sort) {
        case 'POWER':
          return b.power - a.power
        case 'LEVEL':
          return b.level - a.level
        case 'RARITY':
          return rarityRank(b.template.rarity) - rarityRank(a.template.rarity)
        case 'RECENT':
          return b.id - a.id
      }
    })
  }, [heroes, filter, sort])

  const selected = filtered.find((h) => h.id === selectedId) ?? filtered[0] ?? null
  const factionChips: Array<{ key: FilterKey; label: string; data?: string }> = [
    { key: 'ALL', label: 'ALL' },
    ...dynamicFactions.map((f) => ({ key: f, label: shortFactionLabel(f), data: f })),
    { key: 'EPIC_PLUS', label: 'EPIC+' },
  ]

  if (!heroes) {
    return (
      <div className="lobby-root" data-faction={playerFaction}>
        <div className="ros-hdr"><span className="title">ROSTER - loading...</span></div>
      </div>
    )
  }

  return (
    <div className="lobby-root" data-faction={playerFaction}>
      <div className="ros-hdr">
        <span className="title">ROSTER - <b>{heroes.length}</b> HEROES</span>
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
            {c.label} - {factionCounts[c.key] ?? 0}
          </button>
        ))}
      </div>

      <div className="ros-sort">
        <span>Sorted by</span>
        <button type="button" className="right" onClick={() => setSort(NEXT_SORT[sort])}>
          {SORT_LABELS[sort]}
        </button>
      </div>

      {selected && (
        <section className="ros-focus" aria-label="selected hero">
          {(() => {
            const up = upgradeInfo(selected, templateShards)
            return (
              <>
          <div className="ros-focus-art">
            {up.ready && <span className="ros-upgrade-dot" title="Upgrade ready" />}
            <HeroPortrait
              code={selected.template.code}
              name={selected.template.name}
              rarity={selected.template.rarity}
              role={selected.template.role}
              faction={selected.template.faction}
              artPriority="card"
              style={{ width: '100%', height: '100%' }}
              imageStyle={{ objectFit: 'contain', objectPosition: 'center bottom', padding: 18 }}
            />
          </div>
          <div className="ros-focus-copy">
            <div className="ros-focus-head">
              <div>
                <div className="ros-focus-kicker">Selected</div>
                <h2>{selected.template.name}</h2>
                <div className="ros-focus-tier">{RARITY_TIER[selected.template.rarity] ?? selected.template.rarity}</div>
              </div>
              <button
                type="button"
                className="ros-open"
                onClick={() => navigate(`/app/roster/${selected.id}`)}
              >
                Sheet
              </button>
            </div>

            <div className="ros-focus-tags">
              <span>{selected.template.rarity}</span>
              <span>{selected.template.role}</span>
              <span>{shortFactionLabel(selected.template.faction)}</span>
            </div>

            <div className="ros-focus-summary" aria-label="selected hero summary">
              <div><strong>{selected.power.toLocaleString()}</strong><span>Power</span></div>
              <div><strong>L{selected.level}</strong><span>Level</span></div>
              <div><strong>{selected.stars}*</strong><span>Stars</span></div>
              <div><strong>S{selected.special_level}</strong><span>Special</span></div>
            </div>

            <div className={`ros-upgrade-strip${up.ready ? ' is-ready' : ''}`}>
              <span>{up.balance.toLocaleString()} shards</span>
              <span>{up.nextAscend}</span>
              <span>{up.nextSkill}</span>
            </div>

            <div className="ros-focus-stats">
              <div className="ros-focus-stats-head">Combat Readout</div>
              <StatLine label="HP" value={selected.hp} />
              <StatLine label="ATK" value={selected.atk} />
              <StatLine label="DEF" value={selected.def} />
              <StatLine label="SPD" value={selected.spd} />
            </div>
          </div>
              </>
            )
          })()}
        </section>
      )}

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
            const isSel = h.id === selected?.id
            const up = upgradeInfo(h, templateShards)
            return (
              <div
                key={h.id}
                className={`ros-card${isSel ? ' sel' : ''}`}
                data-fac={fac}
                onClick={() => setSelectedId(h.id)}
                onDoubleClick={() => navigate(`/app/roster/${h.id}`)}
              >
                <div className="por">
                  {up.ready && <span className="ros-upgrade-dot" title="Upgrade ready" />}
                  <span className="rar">
                    {Array.from({ length: h.stars }).map((_, i) => <i key={i}></i>)}
                  </span>
                  <span className="lv">L{h.level}</span>
                  <div className="fig">
                    <HeroPortrait
                      code={h.template.code}
                      name={h.template.name}
                      rarity={h.template.rarity}
                      role={h.template.role}
                      faction={h.template.faction}
                      artPriority="card"
                      style={{ width: '100%', height: '100%', borderRadius: 0, border: 'none', boxShadow: 'none' }}
                      imageStyle={{ objectFit: 'contain', objectPosition: 'center bottom', padding: 10 }}
                    />
                  </div>
                </div>
                <div className="nm">{h.template.name}</div>
                <div className="ros-card-power">
                  <strong>{h.power.toLocaleString()}</strong>
                  <span>Power</span>
                </div>
                <div className="ros-meta">
                  <span>{h.template.rarity}</span>
                  <span>{h.template.role}</span>
                  <span>{shortFactionLabel(h.template.faction)}</span>
                </div>
                <div className={`ros-shards${up.ready ? ' is-ready' : ''}`}>
                  <span>{up.balance.toLocaleString()} shards</span>
                  <span>{up.cardAscend}</span>
                  <span>{up.cardSkill}</span>
                </div>
                <div className="ros-card-stats">
                  <span>HP {h.hp.toLocaleString()}</span>
                  <span>ATK {h.atk.toLocaleString()}</span>
                  <span>DEF {h.def.toLocaleString()}</span>
                  <span>SPD {h.spd.toLocaleString()}</span>
                  </div>
                <div className="tier-mini">{RARITY_TIER[h.template.rarity] ?? h.template.rarity}</div>
              </div>
            )
          })}
        </div>
      )}

      {selected && (
        <div className="ros-action" onClick={() => navigate(`/app/roster/${selected.id}`)}>
          <span>SELECT - {selected.template.name}</span>
          <span className="arrow">›</span>
        </div>
      )}
    </div>
  )
}

export default RosterV2Route
