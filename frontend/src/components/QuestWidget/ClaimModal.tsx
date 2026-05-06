import { useState } from 'react'
import { claimQuest, type ActiveQuest } from '../../api/quests'
import { toast } from '../../store/ui'

interface Props {
  quest: ActiveQuest
  onClaimed: () => void
  onClose: () => void
}

export function ClaimModal({ quest, onClaimed, onClose }: Props) {
  const [loading, setLoading] = useState(false)

  async function handleClaim(choice: 'epic' | 'gems') {
    setLoading(true)
    try {
      await claimQuest(quest.quest_id, choice)
      toast.success('Reward claimed!')
      onClaimed()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to claim')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--warn)',
        borderRadius: 12, padding: 28, maxWidth: 480, width: '90%',
        boxShadow: '0 0 40px rgba(255,216,107,0.12)',
      }} onClick={e => e.stopPropagation()}>

        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 28, marginBottom: 6 }}>🏆</div>
          <div style={{ color: 'var(--warn)', fontWeight: 800, fontSize: 18, letterSpacing: '0.05em' }}>
            ONBOARDING COMPLETE
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 4 }}>
            {quest.description}
          </div>
        </div>

        {/* Always-granted frame */}
        <div style={{
          background: 'var(--bg-inset)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 14, marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 48, height: 48, border: '2px solid var(--warn)',
            borderRadius: 8, display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: 20,
          }}>🎖️</div>
          <div>
            <div style={{ color: 'var(--warn)', fontWeight: 700, fontSize: 13 }}>
              Survived Onboarding
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 11 }}>
              Exclusive cosmetic frame — not available in the shop
            </div>
          </div>
          <div style={{
            marginLeft: 'auto', background: 'rgba(255,216,107,0.13)',
            color: 'var(--warn)', fontSize: 10, padding: '3px 8px',
            borderRadius: 4, whiteSpace: 'nowrap',
          }}>YOURS</div>
        </div>

        {/* Choice */}
        <div style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Choose one more reward
        </div>
        <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
          {quest.reward.choice.map(opt => (
            <button
              key={opt.id}
              disabled={loading}
              onClick={() => handleClaim(opt.id as 'epic' | 'gems')}
              style={{
                flex: 1, background: 'var(--bg-inset)',
                border: `2px solid ${opt.id === 'epic' ? '#c97aff' : 'var(--border)'}`,
                borderRadius: 8, padding: 14, cursor: 'pointer',
                textAlign: 'center', color: 'var(--text)',
              }}
            >
              <div style={{ fontSize: 22, marginBottom: 6 }}>
                {opt.id === 'epic' ? '⚔️' : '💎'}
              </div>
              <div style={{ color: opt.id === 'epic' ? '#c97aff' : 'var(--accent)', fontWeight: 700, fontSize: 12, marginBottom: 4 }}>
                {opt.label.toUpperCase()}
              </div>
              <div style={{ color: 'var(--muted)', fontSize: 11 }}>{opt.description}</div>
              <div style={{
                marginTop: 10, background: opt.id === 'epic' ? '#c97aff' : 'var(--border)',
                color: opt.id === 'epic' ? '#0b0d10' : 'var(--text)',
                borderRadius: 4, padding: '5px 0', fontWeight: 700, fontSize: 11,
              }}>
                {loading ? '...' : 'CLAIM'}
              </div>
            </button>
          ))}
        </div>

        <div style={{ color: 'var(--muted)', fontSize: 10, textAlign: 'center' }}>
          Reward cannot be changed after claiming.
        </div>
      </div>
    </div>
  )
}
