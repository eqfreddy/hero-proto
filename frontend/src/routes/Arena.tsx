import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchArena, attackArena } from '../api/arena'
import { useNavigate } from 'react-router-dom'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { CoachMark } from '../components/CoachMark'
import { useState, useEffect } from 'react'
import { TicketHeader } from '../components/Arena/TicketHeader'
import { useMe } from '../hooks/useMe'

/** Format seconds as "Xh Ym Zs", collapsing leading zero units. */
function fmtTickCooldown(seconds: number): string {
  if (seconds <= 0) return 'now'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const parts: string[] = []
  if (h > 0) parts.push(`${h}h`)
  if (m > 0 || h > 0) parts.push(`${m}m`)
  parts.push(`${s}s`)
  return parts.join(' ')
}

export function ArenaRoute() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({ queryKey: ['arena'], queryFn: fetchArena })
  const { data: me } = useMe()
  const [attacking, setAttacking] = useState<number | null>(null)

  // Live countdown for ticket regen tick
  const [tickCooldown, setTickCooldown] = useState<number>(
    () => me?.arena_tickets_next_tick_in ?? 0
  )
  useEffect(() => {
    setTickCooldown(me?.arena_tickets_next_tick_in ?? 0)
  }, [me?.arena_tickets_next_tick_in])
  useEffect(() => {
    if (tickCooldown <= 0) return
    const id = setInterval(() => setTickCooldown((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(id)
  }, [tickCooldown])

  if (isLoading) return <SkeletonGrid />

  async function attack(defenderId: number) {
    if ((me?.arena_tickets ?? 0) <= 0) {
      toast.error('Out of arena tickets — wait for regen')
      return
    }
    setAttacking(defenderId)
    try {
      const res = await attackArena(defenderId, [])
      const r = res.rewards ?? { coins: 0, shards: 0, gems: 0 }
      const rewardParts: string[] = []
      if (r.coins > 0) rewardParts.push(`+${r.coins} 🪙`)
      if (r.shards > 0) rewardParts.push(`+${r.shards} ✦`)
      if (r.gems > 0) rewardParts.push(`+${r.gems} 💎`)
      const rewardLine = rewardParts.length ? ` · ${rewardParts.join(' ')}` : ''
      toast.success(`${res.outcome === 'WIN' ? '⚔️ Victory' : '💀 Defeat'}! Rating ${res.rating_delta >= 0 ? '+' : ''}${res.rating_delta}${rewardLine}`)
      qc.invalidateQueries({ queryKey: ['arena'] })
      qc.invalidateQueries({ queryKey: ['me'] })
      navigate(`/battle/${res.battle_id}/replay`)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Attack failed') }
    finally { setAttacking(null) }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Arena</h2>
      {me && <TicketHeader me={me} />}

      {/* Ticket refresh countdown — show when tickets are not full */}
      {me && me.arena_tickets < me.arena_tickets_cap && (
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
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            ⏱ Next ticket in
          </span>
          <span style={{
            fontSize: 13,
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            color: tickCooldown === 0 ? 'var(--good)' : 'var(--accent)',
          }}>
            {fmtTickCooldown(tickCooldown)}
          </span>
        </div>
      )}

      {/* Practice vs AI — placeholder */}
      <div className="card" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14 }}>🤖 Practice vs AI</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
              Test your team against a bot — no rating change, no ticket cost.
            </div>
          </div>
          <button
            className="secondary"
            style={{ fontSize: 12 }}
            onClick={() => toast.success('Coming soon — practice your team against bot opponents')}
          >
            Practice
          </button>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Available Opponents</h3>
        {!data?.opponents?.length
          ? <EmptyState icon="⚔️" message="No opponents available." />
          : data.opponents.map((o, index) => (
            <div key={o.account_id} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>{o.name}</span>
                <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>⚡ {o.defense_power} · ⚔️ {o.arena_rating}</span>
              </div>
              {index === 0 ? (
                <CoachMark
                  screenId="arena"
                  tooltip="Challenge players near your rating. Wins raise your rank."
                  side="left"
                >
                  <button className="primary" style={{ fontSize: 12 }}
                    disabled={!!attacking || (me?.arena_tickets ?? 0) <= 0}
                    title={(me?.arena_tickets ?? 0) <= 0 ? 'Out of tickets — wait for regen' : undefined}
                    onClick={() => attack(o.account_id)}>
                    {attacking === o.account_id ? '…' : 'Attack'}
                  </button>
                </CoachMark>
              ) : (
                <button className="primary" style={{ fontSize: 12 }}
                  disabled={!!attacking || (me?.arena_tickets ?? 0) <= 0}
                  title={(me?.arena_tickets ?? 0) <= 0 ? 'Out of tickets — wait for regen' : undefined}
                  onClick={() => attack(o.account_id)}>
                  {attacking === o.account_id ? '…' : 'Attack'}
                </button>
              )}
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
