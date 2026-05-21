import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { useGuild } from '../../hooks/useGuild'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import type { Raid } from '../../types'

function formatRaidClock(endsAt: string) {
  const msLeft = new Date(endsAt).getTime() - Date.now()
  if (msLeft <= 0) return 'Raid window closed'
  const totalMinutes = Math.ceil(msLeft / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours > 0) return `Clock is running: ${hours}h ${minutes}m left`
  return `Clock is running: ${minutes}m left`
}

export function GuildRaids() {
  const { data: guildData } = useGuild()
  const guild = guildData?.guild
  const navigate = useNavigate()

  const { data: raid } = useQuery<Raid | null>({
    queryKey: ['guild-raid', guild?.id],
    queryFn: () => apiFetch<Raid | null>('/raids/mine'),
    enabled: !!guild,
    refetchInterval: 30_000,
  })

  if (!guild) return <EmptyState icon="🐉" message="Join a guild to raid." />
  if (!raid) return <EmptyState icon="🐉" message="No active raid." hint="Raids auto-start on a schedule." />

  const pct = Math.max(0, Math.round((raid.remaining_hp / raid.max_hp) * 100))

  return (
    <div className="stack">
      <div className="card" style={{ display: 'grid', gap: 12 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h3 style={{ margin: 0 }}>{raid.boss_name}</h3>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              Lvl {raid.boss_level} · Tier {raid.tier} · {raid.state}
            </div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 700 }}>
            {formatRaidClock(raid.ends_at)}
          </div>
        </div>
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 12, overflow: 'hidden', margin: '8px 0' }}>
          <div style={{ height: '100%', borderRadius: 4, background: 'var(--bad)', width: `${pct}%`, transition: 'width 0.3s ease' }} />
        </div>
        <div className="muted" style={{ fontSize: 12 }}>HP: {raid.remaining_hp.toLocaleString()} / {raid.max_hp.toLocaleString()} ({pct}%)</div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 8,
        }}>
          <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-inset)' }}>
            <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Raid team</div>
            <div style={{ fontWeight: 700, fontSize: 18, marginTop: 4 }}>{raid.contributors.length} hitters online</div>
          </div>
          <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-inset)' }}>
            <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Best swing</div>
            <div style={{ fontWeight: 700, fontSize: 16, marginTop: 4 }}>
              {raid.contributors[0]?.name ?? 'No attempts yet'}
            </div>
            {raid.contributors[0]
              ? <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{raid.contributors[0].damage_dealt.toLocaleString()} damage</div>
              : null}
          </div>
        </div>
        {raid.contributors.length > 0 ? (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>Damage Board</h4>
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
        <div className="row" style={{ marginTop: 12, gap: 8 }}>
          <button className="primary" onClick={() => navigate(`/battle/setup?raid_id=${raid.id}`)}>
            ⚔️ Attack Now
          </button>
        </div>
      </div>
    </div>
  )
}
