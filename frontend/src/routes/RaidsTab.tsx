import { useRaid } from '../hooks/useRaid'
import { useQuery } from '@tanstack/react-query'
import { fetchRaidLeaderboard } from '../api/raids'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { useGuild } from '../hooks/useGuild'

function formatRaidClock(endsAt: string) {
  const msLeft = new Date(endsAt).getTime() - Date.now()
  if (msLeft <= 0) return 'Ended'
  const totalMinutes = Math.ceil(msLeft / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    return `${days}d ${hours % 24}h left`
  }
  if (hours > 0) return `${hours}h ${minutes}m left`
  return `${minutes}m left`
}

function stateTone(state: 'ACTIVE' | 'DEFEATED' | 'EXPIRED') {
  if (state === 'DEFEATED') return { label: 'Cleared', color: 'var(--ok)' }
  if (state === 'EXPIRED') return { label: 'Expired', color: 'var(--muted)' }
  return { label: 'Active', color: 'var(--accent)' }
}

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
          <div className="card" style={{ display: 'grid', gap: 12 }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ margin: 0 }}>{raid.boss_name}</h3>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Lvl {raid.boss_level} · Tier {raid.tier} · Ends {formatRaidClock(raid.ends_at)}
                </div>
              </div>
              <div style={{
                padding: '6px 10px',
                borderRadius: 999,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: stateTone(raid.state).color,
                background: 'color-mix(in srgb, var(--panel) 82%, transparent)',
                border: `1px solid color-mix(in srgb, ${stateTone(raid.state).color} 35%, transparent)`,
              }}>
                {stateTone(raid.state).label}
              </div>
            </div>
            <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 12, overflow: 'hidden', margin: '8px 0' }}>
              <div style={{ height: '100%', background: 'var(--bad)', width: `${Math.round((raid.remaining_hp / raid.max_hp) * 100)}%` }} />
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              {raid.remaining_hp.toLocaleString()} / {raid.max_hp.toLocaleString()} HP remaining
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: 8,
            }}>
              <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-inset)' }}>
                <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Current push</div>
                <div style={{ fontWeight: 700, fontSize: 18, marginTop: 4 }}>{raid.contributors.length} raiders committed</div>
              </div>
              <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-inset)' }}>
                <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Top hitter</div>
                <div style={{ fontWeight: 700, fontSize: 16, marginTop: 4 }}>
                  {raid.contributors[0]?.name ?? 'No hits yet'}
                </div>
                {raid.contributors[0]
                  ? <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{raid.contributors[0].damage_dealt.toLocaleString()} damage</div>
                  : null}
              </div>
            </div>
            <button className="primary" style={{ marginTop: 4 }}
              onClick={() => navigate(`/battle/setup?raid_id=${raid.id}`)}>
              ⚔️ Attack With Guild
            </button>
            {raid.contributors.length > 0 ? (
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>Guild Pressure</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {raid.contributors.slice(0, 5).map((entry, index) => (
                    <div key={entry.account_id} className="row" style={{ justifyContent: 'space-between', fontSize: 12 }}>
                      <span><span className="muted">#{index + 1} </span>{entry.name}</span>
                      <span className="muted">{entry.damage_dealt.toLocaleString()} dmg</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
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
