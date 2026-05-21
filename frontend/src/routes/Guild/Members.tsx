import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { searchUsers } from '../../api/friends'
import {
  demoteMember,
  invitePlayer,
  kickMember,
  promoteMember,
  transferLeadership,
} from '../../api/guild'
import { EmptyState } from '../../components/EmptyState'
import { useGuild } from '../../hooks/useGuild'
import { toast } from '../../store/ui'

type SearchHit = {
  id: number
  name: string
  arena_rating: number
  status: string
}

export function GuildMembers() {
  const { data } = useGuild()
  const qc = useQueryClient()
  const guild = data?.guild
  const members = guild?.members ?? []
  const myRole = data?.my_role
  const canInvite = myRole === 'LEADER' || myRole === 'OFFICER'
  const isLeader = myRole === 'LEADER'
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchHit[]>([])
  const [searching, setSearching] = useState(false)
  const [workingId, setWorkingId] = useState<number | null>(null)

  if (!members.length) return <EmptyState icon="👥" message="No members yet." />

  async function refreshGuild() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['guild'] }),
      qc.invalidateQueries({ queryKey: ['guild-applications'] }),
      qc.invalidateQueries({ queryKey: ['guild-invites-outgoing'] }),
    ])
  }

  async function runAction(accountId: number, action: () => Promise<unknown>, success: string) {
    setWorkingId(accountId)
    try {
      await action()
      toast.success(success)
      await refreshGuild()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Guild action failed')
    } finally {
      setWorkingId(null)
    }
  }

  async function search() {
    if (!query.trim()) return
    setSearching(true)
    try {
      const hits = await searchUsers(query.trim())
      const memberIds = new Set(members.map((member) => member.account_id))
      setResults(hits.filter((hit) => !memberIds.has(hit.id)))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="stack" style={{ gap: 6 }}>
      {guild && canInvite && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Invite Player</h3>
          <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
            Search by handle, then send the invite without bouncing through three other menus.
          </div>
          <div className="row" style={{ gap: 8 }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && search()}
              placeholder="Search players..."
              aria-label="Search players"
              style={{ flex: 1 }}
            />
            <button onClick={search} disabled={searching}>{searching ? '...' : 'Search'}</button>
          </div>
          {results.length > 0 && (
            <div className="stack" style={{ gap: 8, marginTop: 12 }}>
              {results.map((result) => (
                <div key={result.id} className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{result.name}</div>
                    <div className="muted" style={{ fontSize: 12 }}>⚔️ {result.arena_rating} · {result.status}</div>
                  </div>
                  <button
                    className="primary"
                    style={{ fontSize: 12 }}
                    disabled={workingId === result.id}
                    onClick={() => runAction(
                      result.id,
                      () => invitePlayer(guild.id, result.id, ''),
                      'Invite sent.',
                    )}
                  >
                    {workingId === result.id ? '...' : 'Invite'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {members.map((m) => (
        <div key={m.account_id} className="card" style={{ padding: '10px 14px' }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div>
              <span style={{ fontWeight: 600 }}>{m.name}</span>
              <span className="pill" style={{ marginLeft: 8, fontSize: 10 }}>{m.role}</span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="muted" style={{ fontSize: 12, display: 'block' }}>⚔️ {m.arena_rating}</span>
              {guild && isLeader && m.role !== 'LEADER' && (
                <div className="row" style={{ gap: 6, marginTop: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                  {m.role === 'MEMBER' ? (
                    <button
                      style={{ fontSize: 11 }}
                      disabled={workingId === m.account_id}
                      onClick={() => runAction(
                        m.account_id,
                        () => promoteMember(guild.id, m.account_id),
                        `${m.name} promoted.`,
                      )}
                    >
                      Promote
                    </button>
                  ) : null}
                  {m.role === 'OFFICER' ? (
                    <button
                      style={{ fontSize: 11 }}
                      disabled={workingId === m.account_id}
                      onClick={() => runAction(
                        m.account_id,
                        () => demoteMember(guild.id, m.account_id),
                        `${m.name} demoted.`,
                      )}
                    >
                      Demote
                    </button>
                  ) : null}
                  <button
                    style={{ fontSize: 11 }}
                    disabled={workingId === m.account_id}
                    onClick={() => runAction(
                      m.account_id,
                      () => transferLeadership(guild.id, m.account_id),
                      `${m.name} now leads the guild.`,
                    )}
                  >
                    Transfer Lead
                  </button>
                  <button
                    style={{ fontSize: 11, color: 'var(--bad)', borderColor: 'var(--bad)' }}
                    disabled={workingId === m.account_id}
                    onClick={() => runAction(
                      m.account_id,
                      () => kickMember(guild.id, m.account_id),
                      `${m.name} removed.`,
                    )}
                  >
                    Kick
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
