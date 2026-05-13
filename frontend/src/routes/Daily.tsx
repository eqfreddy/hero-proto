import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDaily, claimQuest } from '../api/daily'
import { fetchBattlePass } from '../api/battlePass'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { CoachMark } from '../components/CoachMark'
import { useDailyResetCountdown } from '../hooks/useDailyResetCountdown'
import { useMe } from '../hooks/useMe'
import { useNavigate } from 'react-router-dom'

export function DailyRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily })
  const { data: me } = useMe()
  const { data: bp } = useQuery({ queryKey: ['battle-pass'], queryFn: fetchBattlePass })
  const navigate = useNavigate()
  const countdown = useDailyResetCountdown()
  const quests = data ?? []

  // Find the first unclaimed, claimable BP tier (progress-gated)
  const firstUnclaimedBPTier = (() => {
    if (!bp?.active || !bp.season || !bp.progress) return null
    const currentTier = bp.progress.current_tier
    const claimed = new Set(bp.progress.claimed_free)
    for (let t = 1; t <= currentTier; t++) {
      if (!claimed.has(t)) return t
    }
    return null
  })()

  if (isLoading) return <SkeletonGrid count={4} height={70} />
  if (!quests.length) return <EmptyState icon="📋" message="Daily quests reset at midnight UTC." />

  // Login streak — field doesn't exist on Me yet, default to 0
  const streak = (me as unknown as { login_streak_days?: number })?.login_streak_days ?? 0
  const nextMilestone = streak < 7 ? 7 : streak < 30 ? 30 : 100
  const nextMilestoneReward = nextMilestone === 7 ? '+100 gems' : nextMilestone === 30 ? '+1 rare shard' : '+1 epic shard'
  const daysLeft = nextMilestone - streak

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Daily Quests</h2>

      {/* Reset countdown banner */}
      <div style={{
        padding: '8px 14px',
        borderRadius: 'var(--radius)',
        background: 'var(--bg-inset)',
        border: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
      }}>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>⏱ Quests reset in</span>
        <span style={{ fontSize: 13, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--accent)' }}>
          {countdown}
        </span>
      </div>

      {/* Login streak card */}
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14 }}>🔥 Login Streak</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
              {daysLeft === 0
                ? `${nextMilestone}-day milestone reached! Claim your ${nextMilestoneReward}.`
                : `${daysLeft} more day${daysLeft !== 1 ? 's' : ''} to ${nextMilestone}-day reward: ${nextMilestoneReward}`}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 28, fontWeight: 900, lineHeight: 1 }}>{streak}</div>
            <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>day{streak !== 1 ? 's' : ''}</div>
          </div>
        </div>
        {/* Progress bar toward next milestone */}
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 4, marginTop: 10, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 4,
            background: 'var(--warn)',
            width: `${Math.min(100, Math.round((streak / nextMilestone) * 100))}%`,
            transition: 'width 0.4s ease',
          }} />
        </div>
        <div className="muted" style={{ fontSize: 10, marginTop: 4, textAlign: 'right' }}>
          {streak} / {nextMilestone} days
        </div>
      </div>

      {/* Battle Pass teaser card */}
      {bp?.active && bp.season ? (
        <div className="card" style={{ borderColor: 'rgba(255,209,102,0.3)' }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>🎖 Battle Pass — {bp.season.name}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                {firstUnclaimedBPTier !== null
                  ? `Tier ${firstUnclaimedBPTier} reward ready to claim.`
                  : `Tier ${bp.progress?.current_tier ?? 0} of ${bp.season.max_tier} — keep battling for XP.`}
              </div>
            </div>
            <button
              className="primary"
              style={{ fontSize: 12, background: 'var(--warn)', color: '#0b0d10' }}
              onClick={() => navigate('/app/battle-pass')}
            >
              {firstUnclaimedBPTier !== null ? 'Claim reward →' : 'View Pass →'}
            </button>
          </div>
        </div>
      ) : (
        <div className="card" style={{ borderColor: 'rgba(255,209,102,0.2)' }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>🎖 Battle Pass</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>Earn bonus rewards every season by completing battles and quests.</div>
            </div>
            <button className="primary" style={{ fontSize: 12 }} onClick={() => navigate('/app/battle-pass')}>
              View Pass →
            </button>
          </div>
        </div>
      )}
      <CoachMark
        screenId="daily"
        tooltip="Complete daily quests to earn coins and shards. Resets at midnight."
        side="right"
      >
      <div className="stack" style={{ gap: 0 }}>
      {quests.map((q) => (
        <div key={q.id} className="card" style={{ padding: '12px 14px' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{q.kind.replace(/_/g, ' ')}</div>
              <div style={{ marginTop: 4 }}>
                <div style={{ background: 'var(--bg-inset)', borderRadius: 3, height: 6, width: 180, overflow: 'hidden' }}>
                  <div style={{ height: '100%', background: q.status === 'COMPLETE' ? 'var(--good)' : 'var(--accent)', width: `${Math.min(100, (q.progress / q.goal) * 100)}%` }} />
                </div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{q.progress}/{q.goal}</div>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: 'var(--warn)', marginBottom: 6 }}>
                {q.reward_coins > 0 && `🪙 ${q.reward_coins} `}
                {q.reward_gems > 0 && `💎 ${q.reward_gems} `}
                {q.reward_shards > 0 && `✦ ${q.reward_shards}`}
              </div>
              {q.status === 'COMPLETE' && (
                <button className="primary" style={{ fontSize: 12 }}
                  onClick={async () => {
                    try { await claimQuest(q.id); toast.success('Claimed!'); qc.invalidateQueries({ queryKey: ['daily'] }); qc.invalidateQueries({ queryKey: ['me'] }) }
                    catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                  }}>Claim</button>
              )}
              {q.status === 'CLAIMED' && <span className="muted" style={{ fontSize: 12 }}>✓ Claimed</span>}
            </div>
          </div>
        </div>
      ))}
      </div>
      </CoachMark>
    </div>
  )
}
