import { useQuery } from '@tanstack/react-query'
import { fetchAchievements } from '../api/achievements'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function AchievementsRoute() {
  const { data, isLoading } = useQuery({ queryKey: ['achievements'], queryFn: fetchAchievements })

  if (isLoading) return <SkeletonGrid />
  if (!data) return <EmptyState icon="🏆" message="Achievements unavailable." />

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>🏆 Achievements</h2>
        <span className="muted" style={{ fontSize: 12 }}>{data.unlocked}/{data.total} unlocked</span>
      </div>
      {data.items.map((a) => (
        <div key={a.code} className="card" style={{ padding: '12px 14px', opacity: a.unlocked ? 1 : 0.6 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13 }}>{a.unlocked ? '✅ ' : ''}{a.title}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{a.description}</div>
            </div>
            {!a.unlocked && a.goal > 1 && (
              <div style={{ textAlign: 'right', minWidth: 60 }}>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{a.progress}/{a.goal}</div>
                <div style={{ background: 'var(--bg-inset)', height: 4, borderRadius: 2, marginTop: 3, width: 60 }}>
                  <div style={{ height: '100%', background: 'var(--accent)', borderRadius: 2, width: `${Math.min(100, (a.progress / a.goal) * 100)}%` }} />
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
