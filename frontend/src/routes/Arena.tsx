import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchArena, attackArena } from '../api/arena'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { CoachMark } from '../components/CoachMark'
import { TicketHeader } from '../components/Arena/TicketHeader'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'

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
  const { data: heroes } = useHeroes()
  const [attacking, setAttacking] = useState<number | null>(null)
  const [tickCooldown, setTickCooldown] = useState<number>(() => me?.arena_tickets_next_tick_in ?? 0)

  const attackTeam = [...(heroes ?? [])]
    .sort((a, b) => b.power - a.power)
    .slice(0, 3)
    .map((hero) => hero.id)

  useEffect(() => {
    setTickCooldown(me?.arena_tickets_next_tick_in ?? 0)
  }, [me?.arena_tickets_next_tick_in])

  useEffect(() => {
    if (tickCooldown <= 0) return
    const id = setInterval(() => setTickCooldown((seconds) => Math.max(0, seconds - 1)), 1000)
    return () => clearInterval(id)
  }, [tickCooldown])

  if (isLoading) return <SkeletonGrid />

  async function attack(defenderId: number) {
    if ((me?.arena_tickets ?? 0) <= 0) {
      toast.error('Out of arena tickets â€” wait for regen')
      return
    }
    if (attackTeam.length === 0) {
      toast.error('No arena team available â€” recruit or level a team first')
      return
    }

    setAttacking(defenderId)
    try {
      const res = await attackArena(defenderId, attackTeam)
      const rewards = res.rewards ?? { coins: 0, shards: 0, gems: 0 }
      const rewardParts: string[] = []
      if (rewards.coins > 0) rewardParts.push(`+${rewards.coins} coins`)
      if (rewards.shards > 0) rewardParts.push(`+${rewards.shards} shards`)
      if (rewards.gems > 0) rewardParts.push(`+${rewards.gems} gems`)
      const rewardLine = rewardParts.length ? ` Â· ${rewardParts.join(' ')}` : ''
      toast.success(`${res.outcome === 'WIN' ? 'Victory' : 'Defeat'}! Rating ${res.rating_delta >= 0 ? '+' : ''}${res.rating_delta}${rewardLine}`)
      qc.invalidateQueries({ queryKey: ['arena'] })
      qc.invalidateQueries({ queryKey: ['me'] })
      navigate(`/battle/${res.id}/replay`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Attack failed')
    } finally {
      setAttacking(null)
    }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Arena</h2>
      {me && <TicketHeader me={me} />}

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
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>â± Next ticket in</span>
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

      <div className="card" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14 }}>Scout Run</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
              Warm up comps, check speed tuning, and rehearse the turn flow without dumping rating.
            </div>
          </div>
          <button
            className="secondary"
            style={{ fontSize: 12 }}
            onClick={() => toast.success('Scout queue is next up. For now, hit live fights when tickets are capped and swing back after refresh.')}
          >
            Open Scout Queue
          </button>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Available Opponents</h3>
        {!data?.opponents?.length ? (
          <div style={{
            padding: '18px 16px',
            borderRadius: 'var(--radius)',
            background: 'var(--bg-inset)',
            border: '1px solid var(--border)',
          }}>
            <div style={{ fontWeight: 700, fontSize: 13 }}>Matchmaking is refreshing.</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              No valid rivals right now. Tickets still regen, and a fresh defense list should show up on the next pull.
            </div>
          </div>
        ) : data.opponents.map((opponent, index) => (
          <div key={opponent.account_id} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <span style={{ fontWeight: 600 }}>{opponent.name}</span>
              <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>âš¡ {opponent.defense_power} Â· âš”ï¸ {opponent.arena_rating}</span>
            </div>
            {index === 0 ? (
              <CoachMark
                screenId="arena"
                tooltip="Challenge players near your rating. Wins raise your rank."
                side="left"
              >
                <button
                  className="primary"
                  style={{ fontSize: 12 }}
                  disabled={!!attacking || (me?.arena_tickets ?? 0) <= 0 || attackTeam.length === 0}
                  title={(me?.arena_tickets ?? 0) <= 0 ? 'Out of tickets â€” wait for regen' : attackTeam.length === 0 ? 'No roster team ready yet' : undefined}
                  onClick={() => attack(opponent.account_id)}
                >
                  {attacking === opponent.account_id ? 'â€¦' : 'Attack'}
                </button>
              </CoachMark>
            ) : (
              <button
                className="primary"
                style={{ fontSize: 12 }}
                disabled={!!attacking || (me?.arena_tickets ?? 0) <= 0 || attackTeam.length === 0}
                title={(me?.arena_tickets ?? 0) <= 0 ? 'Out of tickets â€” wait for regen' : attackTeam.length === 0 ? 'No roster team ready yet' : undefined}
                onClick={() => attack(opponent.account_id)}
              >
                {attacking === opponent.account_id ? 'â€¦' : 'Attack'}
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Queue Rhythm</h3>
        <div className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>
          Best loop right now: spend down capped tickets, check recent results, then leave once the board dries up instead of staring at an empty ladder.
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Leaderboard</h3>
        {data?.leaderboard?.map((entry, index) => (
          <div key={entry.account_id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
            <span><span className="muted" style={{ marginRight: 8 }}>#{index + 1}</span>{entry.name}</span>
            <span className="muted">{entry.arena_rating} Â· {entry.wins}W {entry.losses}L</span>
          </div>
        ))}
      </div>

      {data?.recent?.length ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent Matches</h3>
          {data.recent.map((match) => (
            <div key={match.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
              <span style={{ color: match.outcome === 'WIN' ? 'var(--good)' : 'var(--bad)' }}>{match.outcome}</span>
              <span className="muted">vs {match.opponent_name}</span>
              <span style={{ color: match.rating_delta >= 0 ? 'var(--good)' : 'var(--bad)' }}>
                {match.rating_delta >= 0 ? '+' : ''}{match.rating_delta}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
