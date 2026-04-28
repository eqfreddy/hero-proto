import { useQuery } from '@tanstack/react-query'
import { fetchStory } from '../api/story'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function StoryRoute() {
  const { data, isLoading } = useQuery({ queryKey: ['story'], queryFn: fetchStory })

  if (isLoading) return <SkeletonGrid count={3} height={80} />
  if (!data) return <EmptyState icon="📖" message="Story unavailable." />

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>📖 Story</h2>
      <div className="card">
        <div style={{ fontSize: 13 }}>Account Level <strong>{data.account_level}</strong></div>
        <div style={{ background: 'var(--bg-inset)', height: 6, borderRadius: 3, marginTop: 6 }}>
          <div style={{ height: '100%', background: 'var(--accent)', borderRadius: 3, width: `${Math.min(100, (data.account_xp % 100))}%` }} />
        </div>
      </div>
      {data.chapters.map((ch) => (
        <div key={ch.chapter} className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 700 }}>{ch.title}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {ch.cleared_count}/{ch.stage_count} stages cleared
                {ch.completed && !ch.reward_claimed && ' · 🎁 Reward available!'}
                {ch.reward_claimed && ' · ✅ Reward claimed'}
              </div>
            </div>
            <span style={{ color: ch.completed ? 'var(--good)' : 'var(--muted)', fontSize: 20 }}>
              {ch.completed ? '✅' : '🔒'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
