import { useRaid } from '../hooks/useRaid'
import { useQuery } from '@tanstack/react-query'
import { fetchRaidLeaderboard } from '../api/raids'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function RaidsTabRoute() {
  const { data: raid, isLoading } = useRaid()
  const navigate = useNavigate()
  const { data: leaderboard } = useQuery({ queryKey: ['raid-leaderboard'], queryFn: fetchRaidLeaderboard })

  if (isLoading) return <SkeletonGrid count={2} height={100} />

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>🐉 Raid</h2>
      {!raid
        ? <EmptyState icon="🐉" message="No active raid." hint="Raids auto-start on schedule. Join a guild to participate." />
        : (
          <div className="card">
            <h3 style={{ marginTop: 0 }}>{raid.boss_name}</h3>
            <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 12, overflow: 'hidden', margin: '8px 0' }}>
              <div style={{ height: '100%', background: 'var(--bad)', width: `${Math.round((raid.remaining_hp / raid.max_hp) * 100)}%` }} />
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              {raid.remaining_hp.toLocaleString()} / {raid.max_hp.toLocaleString()} HP remaining
            </div>
            <button className="primary" style={{ marginTop: 12 }}
              onClick={() => navigate(`/battle/setup?raid_id=${raid.id}`)}>
              ⚔️ Attack
            </button>
          </div>
        )
      }
      {leaderboard?.length ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Top Contributors (7 days)</h3>
          {leaderboard.slice(0, 10).map((e, i) => (
            <div key={e.account_id} className="row" style={{ justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
              <span><span className="muted">#{i + 1} </span>{e.name}</span>
              <span className="muted">{e.total_damage.toLocaleString()} dmg</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
