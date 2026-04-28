import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchActiveEvent, claimEventQuest, redeemMilestone } from '../api/events'
import { toast } from '../store/ui'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function EventRoute() {
  const qc = useQueryClient()
  const { data: event, isLoading } = useQuery({
    queryKey: ['active-event-detail'],
    queryFn: fetchActiveEvent,
    refetchInterval: 60_000,
  })

  if (isLoading) return <SkeletonGrid count={3} height={80} />
  if (!event) return <EmptyState icon="⚡" message="No active event." hint="Events run during special periods." />

  const endsIn = Math.max(0, Math.floor((new Date(event.ends_at).getTime() - Date.now()) / 1000 / 3600))

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>⚡ {event.display_name}</h2>
        <span className="muted" style={{ fontSize: 12 }}>Ends in ~{endsIn}h · {event.currency_emoji} {event.currency_balance}</span>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Quests</h3>
        {event.quests.map((q) => (
          <div key={q.code} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{q.title}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{q.progress}/{q.goal} · +{q.currency_reward} {event.currency_emoji}</div>
            </div>
            {q.completed && !q.claimed && (
              <button className="primary" style={{ fontSize: 12 }}
                onClick={async () => {
                  try { await claimEventQuest(event.id, q.code); toast.success('Claimed!'); qc.invalidateQueries({ queryKey: ['active-event-detail'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Claim</button>
            )}
            {q.claimed && <span className="muted" style={{ fontSize: 11 }}>✓</span>}
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Milestones</h3>
        {event.milestones.map((m) => (
          <div key={m.idx} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', opacity: m.redeemed ? 0.5 : 1 }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{m.title}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{m.cost} {event.currency_emoji}</div>
            </div>
            {!m.redeemed && m.affordable && (
              <button className="primary" style={{ fontSize: 12 }}
                onClick={async () => {
                  try { await redeemMilestone(event.id, m.idx); toast.success('Redeemed!'); qc.invalidateQueries({ queryKey: ['active-event-detail'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Redeem</button>
            )}
            {m.redeemed && <span className="muted" style={{ fontSize: 11 }}>✓</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
