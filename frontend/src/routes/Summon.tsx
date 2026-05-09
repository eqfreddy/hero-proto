import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { pullStandard } from '../api/summon'
import { fetchFriendPoints, summonFriendBanner } from '../api/friendPoints'
import { useQuery } from '@tanstack/react-query'
import { toast } from '../store/ui'
import { HeroCard } from '../components/HeroCard'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { CoachMark } from '../components/CoachMark'
import type { Hero } from '../types'

const PITY_CAP = 50
const SOFT_PITY = 35

export function SummonRoute() {
  const { data: me, isLoading } = useMe()
  const { data: heroes } = useHeroes()
  const qc = useQueryClient()
  const [pulling, setPulling] = useState(false)
  const [lastPull, setLastPull] = useState<Hero[] | null>(null)
  const { data: fp } = useQuery({ queryKey: ['friend-points'], queryFn: fetchFriendPoints, refetchInterval: 60_000 })

  async function pullFriend() {
    setPulling(true)
    setLastPull(null)
    try {
      const res = await summonFriendBanner()
      setLastPull([res.hero])
      toast.success(`Friend pull: ${res.rarity} ${res.hero.template.name}`)
      qc.invalidateQueries({ queryKey: ['friend-points'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Friend pull failed')
    } finally {
      setPulling(false)
    }
  }

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
          <span className="muted" style={{ fontSize: 12 }}>
            {pityProgress} / {PITY_CAP} — {pullsToEpic} to guaranteed EPIC
            {pityProgress >= SOFT_PITY && (
              <span style={{ color: 'var(--warn)', marginLeft: 6 }}>
                · 🔥 +{Math.min(100, (pityProgress - SOFT_PITY + 1) * 5)}% Epic
              </span>
            )}
          </span>
        </div>
        <div style={{ position: 'relative', background: 'var(--bg-inset)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
          {/* Soft-pity zone marker */}
          <div style={{
            position: 'absolute', left: `${(SOFT_PITY / PITY_CAP) * 100}%`, top: 0,
            width: 1, height: '100%', background: 'rgba(255, 187, 51, 0.6)',
          }} />
          <div style={{
            height: '100%', borderRadius: 4,
            background: 'linear-gradient(90deg, var(--r-rare), var(--r-epic))',
            width: `${Math.min(100, (pityProgress / PITY_CAP) * 100)}%`,
            transition: 'width 0.3s ease',
          }} />
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          Soft pity kicks in at pull {SOFT_PITY} — every pull after adds +5% Epic chance.
          Event banner pulls also count toward this counter.
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Standard Banner</h3>
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          Wallet: ✦ {me?.shards ?? 0} shards · 🎟️ {me?.free_summon_credits ?? 0} free
        </div>
        <div className="row" style={{ gap: 8 }}>
          <CoachMark
            screenId="summon"
            tooltip="Spend shards to summon heroes. Pity guarantees an Epic at 50 pulls."
            side="left"
          >
            <button className="primary" onClick={() => pull(1)} disabled={pulling}>
              {pulling ? '…' : 'Pull ×1 (1 shard)'}
            </button>
          </CoachMark>
          <button className="primary" onClick={() => pull(10)} disabled={pulling}>
            {pulling ? '…' : 'Pull ×10 (10 shards)'}
          </button>
        </div>
      </div>

      {fp && (
        <div className="card" style={{
          borderLeft: '3px solid #ff79c6',
          background: 'linear-gradient(120deg, rgba(255,121,198,0.06), transparent 60%)',
        }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, color: '#ff79c6' }}>Friend Banner</h3>
            <span className="muted" style={{ fontSize: 12 }}>
              💞 {fp.balance} FP · pity {fp.fp_pulls_since_epic}/{fp.fp_pity_threshold}
            </span>
          </div>
          <div className="muted" style={{ fontSize: 12, margin: '8px 0' }}>
            Spend {fp.fp_per_summon} FP per pull. Earn FP by daily-pinging friends.
          </div>
          <button
            className="primary"
            onClick={pullFriend}
            disabled={pulling || fp.balance < fp.fp_per_summon}
          >
            {pulling ? '…' : `Pull (${fp.fp_per_summon} FP)`}
          </button>
        </div>
      )}

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
