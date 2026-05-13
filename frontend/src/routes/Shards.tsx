import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  fetchTemplateShards,
  SHARDS_TO_ASCEND_FROM,
  SHARDS_TO_SKILL_UP,
} from '../api/heroes'
import { useHeroes } from '../hooks/useHeroes'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import type { Hero } from '../types'

type RarityKey = 'LEGENDARY' | 'EPIC' | 'RARE' | 'UNCOMMON' | 'COMMON' | 'MYTH'

const RARITY_ORDER: RarityKey[] = ['MYTH', 'LEGENDARY', 'EPIC', 'RARE', 'UNCOMMON', 'COMMON']

const RARITY_COLOR: Record<RarityKey, string> = {
  MYTH: '#ff5e7e',
  LEGENDARY: '#f39c12',
  EPIC: '#9b59b6',
  RARE: '#3498db',
  UNCOMMON: '#2ecc71',
  COMMON: '#95a5a6',
}

type Filter = 'ALL' | 'CAN_ASCEND' | 'CAN_SKILL_UP'

interface ShardRow {
  code: string
  name: string
  rarity: RarityKey
  balance: number
  hero: Hero  // best-instance / canonical hero of this template (post-remap there is only one)
  nextAscendCost: number | null  // null if at max stars
  nextSkillCost: number | null   // null if at max skill level
  canAscendNow: boolean
  canSkillUpNow: boolean
}

export default function ShardsRoute() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('ALL')

  const { data: shards, isLoading: shardsLoading } = useQuery({
    queryKey: ['template-shards'],
    queryFn: fetchTemplateShards,
  })
  const { data: heroes, isLoading: heroesLoading } = useHeroes()

  const rows = useMemo<ShardRow[]>(() => {
    if (!shards || !heroes) return []
    const heroByCode = new Map<string, Hero>()
    for (const h of heroes) heroByCode.set(h.template.code, h)

    const out: ShardRow[] = []
    for (const [code, balance] of Object.entries(shards)) {
      const hero = heroByCode.get(code)
      if (!hero || balance <= 0) continue  // shards without an owned canonical are an edge case
      const nextAscendCost = hero.stars < 6 ? (SHARDS_TO_ASCEND_FROM[hero.stars] ?? null) : null
      const nextSkillCost = SHARDS_TO_SKILL_UP[hero.special_level] ?? null
      out.push({
        code,
        name: hero.template.name,
        rarity: hero.template.rarity as RarityKey,
        balance,
        hero,
        nextAscendCost,
        nextSkillCost,
        canAscendNow: nextAscendCost != null && balance >= nextAscendCost,
        canSkillUpNow: nextSkillCost != null && balance >= nextSkillCost,
      })
    }
    return out.sort((a, b) => {
      const ra = RARITY_ORDER.indexOf(a.rarity)
      const rb = RARITY_ORDER.indexOf(b.rarity)
      if (ra !== rb) return ra - rb
      return b.balance - a.balance
    })
  }, [shards, heroes])

  const filtered = useMemo(() => {
    if (filter === 'ALL') return rows
    if (filter === 'CAN_ASCEND') return rows.filter((r) => r.canAscendNow)
    return rows.filter((r) => r.canSkillUpNow)
  }, [rows, filter])

  const isLoading = shardsLoading || heroesLoading
  if (isLoading) return <SkeletonGrid count={6} height={88} />

  const totalShards = rows.reduce((s, r) => s + r.balance, 0)
  const readyCount = rows.filter((r) => r.canAscendNow || r.canSkillUpNow).length

  return (
    <div style={{ padding: 12, maxWidth: 960, margin: '0 auto' }}>
      <div className="row" style={{ alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>💎 Hero Shards</h2>
        <div className="muted" style={{ fontSize: 12 }}>
          {totalShards.toLocaleString()} total · {readyCount} ready to upgrade
        </div>
      </div>

      <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
        Duplicate pulls grant shards. Spend them to ascend (stars) or skill up (special). Costs:
        ascend 10 / 30 / 80 / 200 / 500 per tier; skill 5 / 15 / 40 / 100 per level.
      </p>

      <div className="row" style={{ gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {(['ALL', 'CAN_ASCEND', 'CAN_SKILL_UP'] as const).map((k) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={filter === k ? 'primary' : 'secondary'}
            style={{ fontSize: 12 }}
          >
            {k === 'ALL' ? `All (${rows.length})`
              : k === 'CAN_ASCEND' ? `⭐ Ascend ready (${rows.filter((r) => r.canAscendNow).length})`
              : `🔮 Skill ready (${rows.filter((r) => r.canSkillUpNow).length})`}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon="💎"
          message={filter === 'ALL' ? 'No shards yet' : 'Nothing ready'}
          hint={filter === 'ALL'
            ? 'Pull duplicates from the summon banners to start earning shards for each hero.'
            : 'Keep collecting shards — none of your heroes can upgrade with their current balance.'}
        />
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {filtered.map((r) => (
            <div
              key={r.code}
              className="card"
              style={{
                display: 'grid',
                gridTemplateColumns: '48px 1fr auto',
                gap: 12,
                alignItems: 'center',
                padding: 12,
                borderLeft: `4px solid ${RARITY_COLOR[r.rarity]}`,
                cursor: 'pointer',
              }}
              onClick={() => navigate(`/app/roster/${r.hero.id}`)}
            >
              {r.hero.has_bust ? (
                <img
                  src={`/app/static/heroes/busts/${r.code}.png`}
                  alt=""
                  style={{ width: 48, height: 48, borderRadius: 6, objectFit: 'cover', background: 'var(--bg-inset)' }}
                />
              ) : (
                <div style={{
                  width: 48, height: 48, borderRadius: 6,
                  background: RARITY_COLOR[r.rarity],
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 20, fontWeight: 700, color: '#fff',
                }}>
                  {r.name[0]}
                </div>
              )}

              <div>
                <div style={{ fontWeight: 600 }}>
                  {r.name}
                  <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>
                    {r.hero.stars}★ · skill {r.hero.special_level}
                  </span>
                </div>
                <div className="row" style={{ gap: 12, fontSize: 11, marginTop: 4 }}>
                  <span style={{ color: r.canAscendNow ? '#2ecc71' : 'var(--muted)' }}>
                    {r.nextAscendCost == null
                      ? '⭐ Max stars'
                      : `⭐ ${r.balance}/${r.nextAscendCost} → ${r.hero.stars + 1}★`}
                  </span>
                  <span style={{ color: r.canSkillUpNow ? '#2ecc71' : 'var(--muted)' }}>
                    {r.nextSkillCost == null
                      ? '🔮 Max skill'
                      : `🔮 ${r.balance}/${r.nextSkillCost} → skill ${r.hero.special_level + 1}`}
                  </span>
                </div>
              </div>

              <div style={{ textAlign: 'right', fontSize: 24, fontWeight: 700, color: RARITY_COLOR[r.rarity] }}>
                {r.balance}
                <div className="muted" style={{ fontSize: 10, fontWeight: 400 }}>shards</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
