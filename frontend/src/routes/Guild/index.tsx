import { Outlet } from 'react-router-dom'
import { SubNav } from '../../components/SubNav'
import { useGuild } from '../../hooks/useGuild'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  acceptApplication,
  acceptInvite,
  applyToGuild,
  cancelInvite,
  createGuild,
  fetchAllGuilds,
  fetchGuildApplications,
  fetchMyApplications,
  fetchMyInvites,
  fetchOutgoingInvites,
  leaveGuild,
  rejectApplication,
  rejectInvite,
  withdrawApplication,
} from '../../api/guild'
import { toast } from '../../store/ui'
import { SkeletonGrid } from '../../components/SkeletonGrid'
import { CoachMark } from '../../components/CoachMark'
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

async function refreshGuildQueries(qc: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    qc.invalidateQueries({ queryKey: ['guild'] }),
    qc.invalidateQueries({ queryKey: ['guilds-all'] }),
    qc.invalidateQueries({ queryKey: ['guild-applications-mine'] }),
    qc.invalidateQueries({ queryKey: ['guild-invites-mine'] }),
    qc.invalidateQueries({ queryKey: ['guild-applications'] }),
    qc.invalidateQueries({ queryKey: ['guild-invites-outgoing'] }),
  ])
}

export function GuildJoinCreate() {
  const qc = useQueryClient()
  const { data: allGuilds } = useQuery<Guild[]>({ queryKey: ['guilds-all'], queryFn: fetchAllGuilds })
  const { data: myApplications } = useQuery({
    queryKey: ['guild-applications-mine'],
    queryFn: fetchMyApplications,
  })
  const { data: myInvites } = useQuery({
    queryKey: ['guild-invites-mine'],
    queryFn: fetchMyInvites,
  })
  const [newName, setNewName] = useState('')
  const [newTag, setNewTag] = useState('')
  const [creating, setCreating] = useState(false)
  const pendingGuildIds = new Set((myApplications ?? []).filter((a) => a.status === 'PENDING').map((a) => a.guild_id))

  async function doCreate() {
    setCreating(true)
    try {
      await createGuild(newName, newTag, '')
      toast.success(`Guild [${newTag}] created!`)
      await refreshGuildQueries(qc)
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
      {!!myInvites?.length && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Incoming Invites</h3>
          <div className="stack" style={{ gap: 8 }}>
            {myInvites.filter((invite) => invite.status === 'PENDING').map((invite) => (
              <div key={invite.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 700 }}>[{invite.guild_tag}] {invite.guild_name}</div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                      Invited by {invite.inviter_name}{invite.message ? ` · "${invite.message}"` : ''}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    <button className="primary" style={{ fontSize: 12 }} onClick={async () => {
                      try {
                        await acceptInvite(invite.id)
                        toast.success('Invite accepted.')
                        await refreshGuildQueries(qc)
                      } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                    }}>Accept</button>
                    <button style={{ fontSize: 12 }} onClick={async () => {
                      try {
                        await rejectInvite(invite.id)
                        toast.success('Invite declined.')
                        await refreshGuildQueries(qc)
                      } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                    }}>Decline</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {!!myApplications?.length && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Pending Applications</h3>
          <div className="stack" style={{ gap: 8 }}>
            {myApplications.map((app) => {
              const guild = allGuilds?.find((entry) => entry.id === app.guild_id)
              return (
                <div key={app.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>
                        {guild ? `[${guild.tag}] ${guild.name}` : `Guild #${app.guild_id}`}
                        <span className="pill" style={{ marginLeft: 8, fontSize: 10 }}>{app.status}</span>
                      </div>
                      <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                        {app.message || 'No message attached.'}
                      </div>
                    </div>
                    {app.status === 'PENDING' ? (
                      <button style={{ fontSize: 12 }} onClick={async () => {
                        try {
                          await withdrawApplication(app.id)
                          toast.success('Application withdrawn.')
                          await refreshGuildQueries(qc)
                        } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                      }}>Withdraw</button>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
      {allGuilds && allGuilds.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Join a Guild</h3>
          <div className="stack" style={{ gap: 6 }}>
            {allGuilds.map((g, index) => (
              <div key={g.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <span style={{ fontWeight: 700 }}>[{g.tag}] {g.name}</span>
                  <span className="muted" style={{ fontSize: 11, marginLeft: 8 }}>{g.member_count} members</span>
                </div>
                {index === 0 ? (
                  <CoachMark
                    screenId="guild"
                    tooltip="Join a guild to access raids and guild chat."
                    side="left"
                  >
                    <button style={{ fontSize: 12 }} disabled={pendingGuildIds.has(g.id)} onClick={async () => {
                      try {
                        await applyToGuild(g.id, '')
                        toast.success('Application sent!')
                        await refreshGuildQueries(qc)
                      } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                    }}>{pendingGuildIds.has(g.id) ? 'Applied' : 'Apply'}</button>
                  </CoachMark>
                ) : (
                  <button style={{ fontSize: 12 }} disabled={pendingGuildIds.has(g.id)} onClick={async () => {
                    try {
                      await applyToGuild(g.id, '')
                      toast.success('Application sent!')
                      await refreshGuildQueries(qc)
                    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                  }}>{pendingGuildIds.has(g.id) ? 'Applied' : 'Apply'}</button>
                )}
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
  const myRole = data?.my_role
  const canReview = myRole === 'LEADER' || myRole === 'OFFICER'
  const { data: applications } = useQuery({
    queryKey: ['guild-applications', guild?.id],
    queryFn: () => fetchGuildApplications(guild!.id),
    enabled: !!guild && canReview,
  })
  const { data: outgoingInvites } = useQuery({
    queryKey: ['guild-invites-outgoing', guild?.id],
    queryFn: () => fetchOutgoingInvites(guild!.id),
    enabled: !!guild && canReview,
  })

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
      {canReview && (
        <div className="card" style={{ display: 'grid', gap: 14 }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0 }}>Officer Inbox</h3>
              <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                Review join requests and clean up invites without leaving the guild screen.
              </div>
            </div>
            <span className="pill" style={{ fontSize: 10 }}>
              {(applications?.length ?? 0) + (outgoingInvites?.length ?? 0)} open
            </span>
          </div>
          <div style={{ display: 'grid', gap: 12 }}>
            <div>
              <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>Pending Applicants</h4>
              {applications?.length ? (
                <div className="stack" style={{ gap: 8 }}>
                  {applications.map((app) => (
                    <div key={app.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                        <div>
                          <div style={{ fontWeight: 700 }}>{app.applicant_name}</div>
                          <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                            {app.message || 'No note left.'}
                          </div>
                        </div>
                        <div className="row" style={{ gap: 8 }}>
                          <button className="primary" style={{ fontSize: 12 }} onClick={async () => {
                            try {
                              await acceptApplication(app.id)
                              toast.success('Applicant accepted.')
                              await refreshGuildQueries(qc)
                            } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                          }}>Accept</button>
                          <button style={{ fontSize: 12 }} onClick={async () => {
                            try {
                              await rejectApplication(app.id)
                              toast.success('Applicant rejected.')
                              await refreshGuildQueries(qc)
                            } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                          }}>Reject</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="muted" style={{ fontSize: 12 }}>No pending applications.</div>
              )}
            </div>
            <div>
              <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>Outgoing Invites</h4>
              {outgoingInvites?.length ? (
                <div className="stack" style={{ gap: 8 }}>
                  {outgoingInvites.map((invite) => (
                    <div key={invite.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                        <div>
                          <div style={{ fontWeight: 700 }}>{invite.invitee_name}</div>
                          <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                            Sent by {invite.inviter_name}{invite.message ? ` · "${invite.message}"` : ''}
                          </div>
                        </div>
                        <button style={{ fontSize: 12 }} onClick={async () => {
                          try {
                            await cancelInvite(invite.id)
                            toast.success('Invite cancelled.')
                            await refreshGuildQueries(qc)
                          } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                        }}>Cancel</button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="muted" style={{ fontSize: 12 }}>No outgoing invites yet.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
