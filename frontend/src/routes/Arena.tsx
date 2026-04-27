import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchArena, attackArena } from '../api/arena'
import { useNavigate } from 'react-router-dom'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { useState } from 'react'

export function ArenaRoute() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({ queryKey: ['arena'], queryFn: fetchArena })
  const [attacking, setAttacking] = useState<number | null>(null)

  if (isLoading) return <SkeletonGrid />

  async function attack(defenderId: number) {
    setAttacking(defenderId)
    try {
      const res = await attackArena(defenderId, [])
      toast.success(`${res.outcome === 'WIN' ? '⚔️ Victory' : '💀 Defeat'}! Rating ${res.rating_delta >= 0 ? '+' : ''}${res.rating_delta}`)
      qc.invalidateQueries({ queryKey: ['arena'] })
      qc.invalidateQueries({ queryKey: ['me'] })
      navigate(`/battle/${res.battle_id}/replay`)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Attack failed') }
    finally { setAttacking(null) }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Arena</h2>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Available Opponents</h3>
        {!data?.opponents?.length
          ? <EmptyState icon="⚔️" message="No opponents available." />
          : data.opponents.map((o) => (
            <div key={o.account_id} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>{o.name}</span>
                <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>⚡ {o.defense_power} · ⚔️ {o.arena_rating}</span>
              </div>
              <button className="primary" style={{ fontSize: 12 }}
                disabled={!!attacking} onClick={() => attack(o.account_id)}>
                {attacking === o.account_id ? '…' : 'Attack'}
              </button>
            </div>
          ))
        }
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Leaderboard</h3>
        {data?.leaderboard?.map((e, i) => (
          <div key={e.account_id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
            <span><span className="muted" style={{ marginRight: 8 }}>#{i + 1}</span>{e.name}</span>
            <span className="muted">{e.arena_rating} · {e.wins}W {e.losses}L</span>
          </div>
        ))}
      </div>

      {data?.recent?.length ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent Matches</h3>
          {data.recent.map((m) => (
            <div key={m.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
              <span style={{ color: m.outcome === 'WIN' ? 'var(--good)' : 'var(--bad)' }}>{m.outcome}</span>
              <span className="muted">vs {m.opponent_name}</span>
              <span style={{ color: m.rating_delta >= 0 ? 'var(--good)' : 'var(--bad)' }}>
                {m.rating_delta >= 0 ? '+' : ''}{m.rating_delta}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
