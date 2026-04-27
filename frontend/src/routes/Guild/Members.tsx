import { useGuild } from '../../hooks/useGuild'
import { EmptyState } from '../../components/EmptyState'

export function GuildMembers() {
  const { data } = useGuild()
  const members = data?.guild?.members ?? []

  if (!members.length) return <EmptyState icon="👥" message="No members yet." />

  return (
    <div className="stack" style={{ gap: 6 }}>
      {members.map((m) => (
        <div key={m.account_id} className="card" style={{ padding: '10px 14px' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <span style={{ fontWeight: 600 }}>{m.name}</span>
              <span className="pill" style={{ marginLeft: 8, fontSize: 10 }}>{m.role}</span>
            </div>
            <span className="muted" style={{ fontSize: 12 }}>⚔️ {m.arena_rating}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
