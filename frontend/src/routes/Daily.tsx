import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDaily, claimQuest } from '../api/daily'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function DailyRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily })
  const quests = data?.quests ?? []

  if (isLoading) return <SkeletonGrid count={4} height={70} />
  if (!quests.length) return <EmptyState icon="📋" message="Daily quests reset at midnight UTC." />

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Daily Quests</h2>
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
  )
}
