import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { useGuild } from '../../hooks/useGuild'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import type { Raid } from '../../types'

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
      <div className="card">
        <h3 style={{ marginTop: 0 }}>{raid.boss_name}</h3>
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 12, overflow: 'hidden', margin: '8px 0' }}>
          <div style={{ height: '100%', borderRadius: 4, background: 'var(--bad)', width: `${pct}%`, transition: 'width 0.3s ease' }} />
        </div>
        <div className="muted" style={{ fontSize: 12 }}>HP: {raid.remaining_hp.toLocaleString()} / {raid.max_hp.toLocaleString()} ({pct}%)</div>
        <div className="row" style={{ marginTop: 12, gap: 8 }}>
          <button className="primary" onClick={() => navigate(`/battle/setup?raid_id=${raid.id}`)}>
            ⚔️ Attack
          </button>
        </div>
      </div>
    </div>
  )
}
