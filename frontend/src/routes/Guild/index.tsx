import { Outlet } from 'react-router-dom'
import { SubNav } from '../../components/SubNav'
import { useGuild } from '../../hooks/useGuild'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { applyToGuild, createGuild, fetchAllGuilds, leaveGuild } from '../../api/guild'
import { toast } from '../../store/ui'
import { SkeletonGrid } from '../../components/SkeletonGrid'
import { useState } from 'react'
import type { Guild } from '../../types'

export function GuildRoute() {
  const { data, isLoading } = useGuild()

  if (isLoading) return <SkeletonGrid count={3} height={80} />

  if (!data?.guild) {
    return <GuildJoinCreate />
  }

  return (
    <div>
      <SubNav tabs={[
        { path: '/app/guild', label: 'Overview' },
        { path: '/app/guild/members', label: 'Members' },
        { path: '/app/guild/chat', label: 'Chat' },
        { path: '/app/guild/raids', label: 'Raids' },
      ]} />
      <Outlet />
    </div>
  )
}

function GuildJoinCreate() {
  const qc = useQueryClient()
  const { data: allGuilds } = useQuery<Guild[]>({ queryKey: ['guilds-all'], queryFn: fetchAllGuilds })
  const [newName, setNewName] = useState('')
  const [newTag, setNewTag] = useState('')
  const [creating, setCreating] = useState(false)

  async function doCreate() {
    setCreating(true)
    try {
      await createGuild(newName, newTag, '')
      toast.success(`Guild [${newTag}] created!`)
      qc.invalidateQueries({ queryKey: ['guild'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setCreating(false) }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Guild</h2>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Create a Guild</h3>
        <div className="stack" style={{ gap: 8 }}>
          <input placeholder="Guild name" value={newName} onChange={e => setNewName(e.target.value)} style={{ width: '100%' }} />
          <input placeholder="Tag (3-5 chars)" value={newTag} onChange={e => setNewTag(e.target.value)} maxLength={5} style={{ width: 120 }} />
          <button className="primary" onClick={doCreate} disabled={creating || !newName || !newTag}>
            {creating ? '…' : 'Create'}
          </button>
        </div>
      </div>
      {allGuilds && allGuilds.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Join a Guild</h3>
          <div className="stack" style={{ gap: 6 }}>
            {allGuilds.map(g => (
              <div key={g.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <span style={{ fontWeight: 700 }}>[{g.tag}] {g.name}</span>
                  <span className="muted" style={{ fontSize: 11, marginLeft: 8 }}>{g.member_count} members</span>
                </div>
                <button style={{ fontSize: 12 }} onClick={async () => {
                  try {
                    await applyToGuild(g.id, '')
                    toast.success('Application sent!')
                    qc.invalidateQueries({ queryKey: ['guild'] })
                  } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Apply</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function GuildOverview() {
  const { data } = useGuild()
  const qc = useQueryClient()
  const guild = data?.guild

  if (!guild) return null

  return (
    <div className="stack">
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ margin: 0 }}>[{guild.tag}] {guild.name}</h2>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{guild.description}</div>
          </div>
          <span className="pill">{guild.member_count} members</span>
        </div>
      </div>
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span style={{ fontSize: 13 }}>Your role: <strong>{data?.my_role}</strong></span>
          <button style={{ fontSize: 12, color: 'var(--bad)', borderColor: 'var(--bad)' }}
            onClick={async () => {
              if (!confirm('Leave guild?')) return
              try { await leaveGuild(guild.id); qc.invalidateQueries({ queryKey: ['guild'] }) }
              catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
            }}>Leave Guild</button>
        </div>
      </div>
    </div>
  )
}
