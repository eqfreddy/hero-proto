import { Outlet } from 'react-router-dom'
import { SubNav } from '../../components/SubNav'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchFriends, searchUsers, sendFriendRequest } from '../../api/friends'
import { toast } from '../../store/ui'
import { useState } from 'react'
import { EmptyState } from '../../components/EmptyState'
import type { Friend } from '../../api/friends'

export function FriendsLayout() {
  return (
    <div>
      <SubNav tabs={[
        { path: '/app/friends', label: 'Friends' },
        { path: '/app/friends/messages', label: 'Messages' },
      ]} />
      <Outlet />
    </div>
  )
}

export function FriendsList() {
  const qc = useQueryClient()
  const { data: friends } = useQuery({ queryKey: ['friends'], queryFn: fetchFriends })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Friend[]>([])
  const [searching, setSearching] = useState(false)

  async function search() {
    if (!query.trim()) return
    setSearching(true)
    try { setResults(await searchUsers(query)) }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Search failed') }
    finally { setSearching(false) }
  }

  return (
    <div className="stack">
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add Friend</h3>
        <div className="row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder="Search by username…"
            style={{ flex: 1 }}
            aria-label="Search users"
          />
          <button onClick={search} disabled={searching}>{searching ? '…' : 'Search'}</button>
        </div>
        {results.map((u) => (
          <div key={u.id} className="row" style={{ justifyContent: 'space-between', marginTop: 8 }}>
            <span>{u.name}</span>
            <button className="primary" style={{ fontSize: 12 }}
              onClick={async () => {
                try { await sendFriendRequest(u.id); toast.success('Request sent!'); qc.invalidateQueries({ queryKey: ['friends'] }) }
                catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
              }}>Add</button>
          </div>
        ))}
      </div>
      {!friends?.length
        ? <EmptyState icon="🤝" message="No friends yet." hint="Search for players above." />
        : friends.map((f) => (
          <div key={f.id} className="card" style={{ padding: '10px 14px' }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 600 }}>{f.name}</span>
              <span className="muted" style={{ fontSize: 12 }}>⚔️ {f.arena_rating}</span>
            </div>
          </div>
        ))
      }
    </div>
  )
}
