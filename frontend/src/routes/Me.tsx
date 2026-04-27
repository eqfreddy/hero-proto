import { useMe } from '../hooks/useMe'
import { useAuthStore } from '../store/auth'
import { useQueryClient } from '@tanstack/react-query'
import { apiPost } from '../api/client'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { useState } from 'react'

export function MeRoute() {
  const { data: me, isLoading } = useMe()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const [claimingBonus, setClaimingBonus] = useState(false)
  const [refilling, setRefilling] = useState(false)

  if (isLoading) return <SkeletonGrid count={4} height={80} />
  if (!me) return <div className="muted">Not signed in.</div>

  async function claimDailyBonus() {
    setClaimingBonus(true)
    try {
      const res = await apiPost<{ reward: Record<string, number> }>('/me/daily-bonus', {})
      const parts = Object.entries(res.reward).filter(([, v]) => v > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Daily bonus: ${parts.join(', ')}` : 'Claimed!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to claim bonus')
    } finally {
      setClaimingBonus(false)
    }
  }

  async function refillEnergy() {
    setRefilling(true)
    try {
      await apiPost('/me/refill-energy', { gems: 50 })
      toast.success('Energy refilled!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to refill')
    } finally {
      setRefilling(false)
    }
  }

  function logout() {
    clearJwt()
    qc.clear()
  }

  return (
    <div className="stack">
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Account</h2>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong>{me.email}</strong>
            <span className="muted"> · id {me.id}</span>
          </div>
          <button onClick={logout} style={{ fontSize: 12 }}>Sign out</button>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Level {me.account_level}</h2>
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 8, overflow: 'hidden', marginTop: 4 }}>
          <div style={{
            height: '100%', borderRadius: 4, background: 'var(--accent)',
            width: `${Math.min(100, (me.account_xp / Math.max(1, me.account_xp + 100)) * 100)}%`,
          }} />
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{me.account_xp} XP</div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Currencies</h2>
        <div className="row" style={{ gap: 24, flexWrap: 'wrap' }}>
          {[
            ['💎', 'Gems', me.gems],
            ['✦', 'Shards', me.shards],
            ['🪙', 'Coins', me.coins.toLocaleString()],
            ['🎫', 'Access Cards', me.access_cards],
            ['🎟️', 'Free Summons', me.free_summon_credits],
          ].map(([icon, label, val]) => (
            <div key={String(label)}>
              <div className="muted" style={{ fontSize: 11 }}>{icon} {label}</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Energy</h2>
            <div style={{ fontSize: 22, fontWeight: 700 }}>⚡ {me.energy} / {me.energy_cap}</div>
          </div>
          <button onClick={refillEnergy} disabled={refilling} className="secondary" style={{ fontSize: 12 }}>
            {refilling ? '…' : 'Refill (50 💎)'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Daily Bonus</h2>
            <div className="muted" style={{ fontSize: 12 }}>Streak login rewards</div>
          </div>
          <button onClick={claimDailyBonus} disabled={claimingBonus} className="primary">
            {claimingBonus ? '…' : 'Claim'}
          </button>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: 14, color: 'var(--muted)' }}>Arena</h2>
        <div className="row" style={{ gap: 24 }}>
          <div><div className="muted" style={{ fontSize: 11 }}>Rating</div><div style={{ fontSize: 20, fontWeight: 700 }}>{me.arena_rating}</div></div>
          <div><div className="muted" style={{ fontSize: 11 }}>W / L</div><div style={{ fontSize: 20, fontWeight: 700 }}>{me.arena_wins} / {me.arena_losses}</div></div>
        </div>
      </div>
    </div>
  )
}
