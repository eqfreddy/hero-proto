import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../store/auth'
import { useMe } from '../hooks/useMe'
import { acknowledgeWeeklyRewards } from '../api/arena'
import { toast } from '../store/ui'

export function PendingArenaReward() {
  const jwt = useAuthStore(s => s.jwt)
  const qc = useQueryClient()
  const { data: me } = useMe()
  const [acking, setAcking] = useState(false)

  const reward = me?.pending_arena_rewards?.[0]
  if (!jwt || !reward) return null

  const isChampion = reward.rank === 1

  async function handleClaim() {
    setAcking(true)
    try {
      await acknowledgeWeeklyRewards()
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to claim')
    } finally {
      setAcking(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 500,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)',
    }}>
      <div style={{
        background: 'var(--bg-card, var(--panel))',
        border: `2px solid ${isChampion ? 'var(--warn)' : 'var(--accent)'}`,
        borderRadius: 12, padding: 24, minWidth: 320, maxWidth: '90vw',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>
          🏆 Arena Week Complete
        </div>
        <div style={{ color: 'var(--muted)', marginBottom: 14 }}>
          You finished rank #{reward.rank} last week
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--accent)', marginBottom: 6 }}>
          +{reward.gems} 💎
        </div>
        {isChampion && (
          <div style={{ fontSize: 13, color: 'var(--warn)', marginBottom: 12 }}>
            Cosmetic frame unlocked: Arena Champion
          </div>
        )}
        <button
          className="primary"
          disabled={acking}
          onClick={handleClaim}
          style={{ marginTop: 14, padding: '8px 24px', fontSize: 14 }}
        >
          {acking ? '...' : 'Claim'}
        </button>
      </div>
    </div>
  )
}
