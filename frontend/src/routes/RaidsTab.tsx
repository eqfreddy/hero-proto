import { useRaid } from '../hooks/useRaid'
import { useQuery } from '@tanstack/react-query'
import { fetchRaidLeaderboard } from '../api/raids'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { useGuild } from '../hooks/useGuild'

export function RaidsTabRoute() {
  const { data: raid, isLoading } = useRaid()
  const navigate = useNavigate()
  const { data: leaderboard } = useQuery({ queryKey: ['raid-leaderboard'], queryFn: fetchRaidLeaderboard })
  const { data: guildData } = useGuild()
  const hasGuild = !!(guildData?.guild)

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

      {/* What are Raids? explainer — always shown when no active raid */}
      <div className="card" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <h3 style={{ marginTop: 0, fontSize: 13 }}>🐉 What are Raids?</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 13, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--accent)', flexShrink: 0 }}>•</span>
            <span>Co-op boss fights with your Guild — deal damage together before the timer runs out.</span>
          </div>
          <div style={{ fontSize: 13, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--accent)', flexShrink: 0 }}>•</span>
            <span>Top 10% damage dealers earn bonus rewards including rare Collection 8-tracks.</span>
          </div>
          <div style={{ fontSize: 13, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--accent)', flexShrink: 0 }}>•</span>
            <span>New Raids spawn weekly on Sundays — keep an eye on your Guild chat for the call.</span>
          </div>
        </div>
      </div>

      {/* Need a Guild? CTA — only shown when the user has no guild */}
      {!hasGuild && (
        <div className="card" style={{
          borderColor: 'rgba(78,184,255,0.3)',
          background: 'linear-gradient(135deg, var(--panel) 0%, color-mix(in srgb, var(--accent) 5%, var(--panel)) 100%)',
        }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>🏰 Need a Guild?</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                Raids require a Guild. Browse open Guilds and join one to participate.
              </div>
            </div>
            <button className="primary" style={{ fontSize: 12 }} onClick={() => navigate('/app/guild')}>
              Find a Guild →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
