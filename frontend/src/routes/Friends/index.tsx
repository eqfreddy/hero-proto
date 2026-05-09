import { Outlet } from 'react-router-dom'
import { SubNav } from '../../components/SubNav'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchFriends, searchUsers, sendFriendRequest } from '../../api/friends'
import { fetchFriendPoints, pingFriend } from '../../api/friendPoints'
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
  const { data: fp } = useQuery({ queryKey: ['friend-points'], queryFn: fetchFriendPoints, refetchInterval: 60_000 })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Friend[]>([])
  const [searching, setSearching] = useState(false)
  const [pinging, setPinging] = useState<number | null>(null)

  async function ping(friendId: number) {
    setPinging(friendId)
    try {
      const r = await pingFriend(friendId)
      toast.success(`+${r.fp_granted} FP for both of you!`)
      qc.invalidateQueries({ queryKey: ['friend-points'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Ping failed')
    } finally {
      setPinging(null)
    }
  }

  async function search() {
    if (!query.trim()) return
    setSearching(true)
    try { setResults(await searchUsers(query)) }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Search failed') }
    finally { setSearching(false) }
  }

  return (
    <div className="stack">
      {fp && (
        <div className="card" style={{
          padding: 12, borderLeft: '3px solid var(--accent)',
          background: 'linear-gradient(120deg, rgba(0,255,224,0.06), transparent 60%)',
        }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 700 }}>
                Friend Points
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
                💞 {fp.balance.toLocaleString()} · {fp.pings_remaining_today}/{fp.pings_daily_cap} pings left today
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                Spend {fp.fp_per_summon} on the friend banner. Pity at {fp.fp_pity_threshold} pulls.
              </div>
            </div>
          </div>
        </div>
      )}
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
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600 }}>{f.name}</span>
              <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                <span className="muted" style={{ fontSize: 12 }}>⚔️ {f.arena_rating}</span>
                <button
                  className="primary"
                  disabled={pinging === f.id || (fp?.pings_remaining_today ?? 0) <= 0}
                  onClick={() => ping(f.id)}
                  style={{ fontSize: 11, padding: '3px 8px' }}
                  title="Daily ping — both of you get +5 FP"
                >
                  {pinging === f.id ? '...' : '💞 Ping'}
                </button>
              </div>
            </div>
          </div>
        ))
      }
    </div>
  )
}
