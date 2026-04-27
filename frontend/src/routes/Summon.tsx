import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { pullStandard } from '../api/summon'
import { toast } from '../store/ui'
import { HeroCard } from '../components/HeroCard'
import { SkeletonGrid } from '../components/SkeletonGrid'
import type { Hero } from '../types'

const PITY_CAP = 50

export function SummonRoute() {
  const { data: me, isLoading } = useMe()
  const { data: heroes } = useHeroes()
  const qc = useQueryClient()
  const [pulling, setPulling] = useState(false)
  const [lastPull, setLastPull] = useState<Hero[] | null>(null)

  if (isLoading) return <SkeletonGrid count={3} height={80} />

  const pityProgress = me?.pulls_since_epic ?? 0
  const pullsToEpic = Math.max(0, PITY_CAP - pityProgress)

  const recent = heroes ? [...heroes].sort((a, b) => b.id - a.id).slice(0, 10) : []

  async function pull(count: 1 | 10) {
    setPulling(true)
    setLastPull(null)
    try {
      const res = await pullStandard(count)
      setLastPull(res.heroes)
      const rarityOrder = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']
      const best = res.heroes.reduce((a, b) =>
        rarityOrder.indexOf(b.template.rarity) > rarityOrder.indexOf(a.template.rarity) ? b : a
      )
      toast.success(`Got ${res.heroes.length} hero${res.heroes.length > 1 ? 'es' : ''}! Best: ${best.template.rarity} ${best.template.name}`)
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Pull failed')
    } finally {
      setPulling(false)
    }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Summon</h2>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Pity Progress</span>
          <span className="muted" style={{ fontSize: 12 }}>{pityProgress} / {PITY_CAP} — {pullsToEpic} to guaranteed EPIC</span>
        </div>
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 4,
            background: 'linear-gradient(90deg, var(--r-rare), var(--r-epic))',
            width: `${Math.min(100, (pityProgress / PITY_CAP) * 100)}%`,
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Standard Banner</h3>
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          Wallet: ✦ {me?.shards ?? 0} shards · 🎟️ {me?.free_summon_credits ?? 0} free
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="primary" onClick={() => pull(1)} disabled={pulling}>
            {pulling ? '…' : 'Pull ×1 (1 shard)'}
          </button>
          <button className="primary" onClick={() => pull(10)} disabled={pulling}>
            {pulling ? '…' : 'Pull ×10 (10 shards)'}
          </button>
        </div>
      </div>

      {lastPull && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Last Pull</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {lastPull.map((h) => <HeroCard key={h.id} hero={h} />)}
          </div>
        </div>
      )}

      {recent.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent ({recent.length})</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {recent.map((h) => <HeroCard key={h.id} hero={h} />)}
          </div>
        </div>
      )}
    </div>
  )
}
