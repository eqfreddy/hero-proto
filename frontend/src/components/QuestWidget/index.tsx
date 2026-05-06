import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchActiveQuests, dismissQuest, type ActiveQuest } from '../../api/quests'
import { ClaimModal } from './ClaimModal'
import { useAuthStore } from '../../store/auth'

export function QuestWidget() {
  const jwt = useAuthStore(s => s.jwt)
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [showClaim, setShowClaim] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  const { data } = useQuery({
    queryKey: ['quests', 'active'],
    queryFn: fetchActiveQuests,
    enabled: !!jwt,
    refetchInterval: 30_000,
  })

  const quest: ActiveQuest | undefined = data?.[0]

  if (!jwt || !quest || dismissed || quest.claimed_at) return null

  const pct = Math.round((quest.done_count / quest.total_count) * 100)
  const isComplete = quest.completed_at !== null
  const nextTask = quest.tasks.find(t => !t.done)

  async function handleDismiss() {
    await dismissQuest(quest!.quest_id)
    setDismissed(true)
    qc.invalidateQueries({ queryKey: ['quests'] })
  }

  return (
    <>
      {showClaim && isComplete && (
        <ClaimModal
          quest={quest}
          onClose={() => setShowClaim(false)}
          onClaimed={() => {
            setShowClaim(false)
            qc.invalidateQueries({ queryKey: ['quests'] })
            qc.invalidateQueries({ queryKey: ['me'] })
          }}
        />
      )}

      <div style={{
        position: 'fixed', bottom: 80, right: 16, zIndex: 200,
        width: expanded ? 240 : 'auto', maxWidth: '90vw',
        background: 'var(--bg-card)',
        border: `1px solid ${isComplete ? 'var(--warn)' : 'var(--accent)'}`,
        borderRadius: 10,
        boxShadow: isComplete
          ? '0 0 16px rgba(255,216,107,0.35)'
          : '0 4px 16px rgba(78,161,255,0.18)',
        animation: isComplete ? 'questGlow 1.5s ease-in-out infinite alternate' : undefined,
        fontSize: 12,
      }}>
        {/* Collapsed pill / header */}
        <div
          style={{ padding: '8px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
          onClick={() => setExpanded(e => !e)}
        >
          <span style={{ color: 'var(--warn)', fontWeight: 700, fontSize: 11 }}>
            ⭐ {quest.name}
          </span>
          {!expanded && (
            <span style={{ color: 'var(--muted)', fontSize: 10 }}>
              · {quest.done_count}/{quest.total_count}
            </span>
          )}
          <span style={{ marginLeft: 'auto', color: 'var(--muted)' }}>
            {expanded ? '▾' : '▸'}
          </span>
        </div>

        {/* Progress bar (always visible) */}
        <div style={{ height: 3, background: 'var(--bg-inset)', margin: '0 12px 8px' }}>
          <div style={{ height: '100%', width: `${pct}%`, background: isComplete ? 'var(--warn)' : 'var(--accent)', borderRadius: 2, transition: 'width 0.3s' }} />
        </div>

        {expanded && (
          <div style={{ padding: '0 12px 10px' }}>
            {/* Task list */}
            <div style={{ maxHeight: 220, overflowY: 'auto' }}>
              {quest.tasks.map(t => (
                <div key={t.id} style={{
                  display: 'flex', alignItems: 'baseline', gap: 6,
                  marginBottom: 4, color: t.done ? 'var(--good)' : t.id === nextTask?.id ? 'var(--accent)' : 'var(--muted)',
                  fontSize: 11,
                }}>
                  <span>{t.done ? '✓' : t.id === nextTask?.id ? '→' : '○'}</span>
                  <span style={{ flex: 1 }}>{t.label}</span>
                  {!t.done && <span style={{ color: 'var(--muted)', fontSize: 10 }}>{t.current}/{t.target}</span>}
                </div>
              ))}
            </div>

            {/* CTA / dismiss */}
            <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
              {isComplete ? (
                <button
                  className="primary"
                  style={{ flex: 1, fontSize: 11, padding: '5px 0' }}
                  onClick={() => setShowClaim(true)}
                >
                  🏆 Claim Reward
                </button>
              ) : null}
              <button
                style={{ fontSize: 10, color: 'var(--danger)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                onClick={handleDismiss}
              >
                ✕ dismiss
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes questGlow {
          from { box-shadow: 0 0 12px rgba(255,216,107,0.25); }
          to   { box-shadow: 0 0 28px rgba(255,216,107,0.55); }
        }
      `}</style>
    </>
  )
}
