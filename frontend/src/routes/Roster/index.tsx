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
