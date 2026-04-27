# SPA Rewrite — Plan 3: Remaining Tabs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the remaining ten tabs — Guild (with sub-routes), Friends (with DMs), Arena, Raids, Daily, Story, Achievements, Event, Crafting, and Account — each hitting the existing JSON API and matching HTMX partial feature parity.

**Architecture:** Each tab follows the same pattern as Plan 2: a route component, TanStack Query hooks, mutation via `apiPost()` + query invalidation. Guild and Friends use nested routes with a sub-nav strip. All tabs import from `src/api/`, `src/hooks/`, `src/components/`.

**Tech Stack:** React 18 + TypeScript, TanStack Query v5, React Router v6, Vitest + RTL

**Prerequisite:** Plan 2 complete — Me, Roster, Stages, Summon, Shop all working.

---

## File map

**Create:**
- `frontend/src/api/guild.ts`
- `frontend/src/api/arena.ts`
- `frontend/src/api/raids.ts`
- `frontend/src/api/friends.ts`
- `frontend/src/api/daily.ts`
- `frontend/src/api/story.ts`
- `frontend/src/api/achievements.ts`
- `frontend/src/api/events.ts`
- `frontend/src/api/crafting.ts`
- `frontend/src/api/account.ts`
- `frontend/src/hooks/useGuild.ts`
- `frontend/src/hooks/useRaid.ts`
- `frontend/src/hooks/useNotifications.ts` (already partially in BellPopover — extract)
- `frontend/src/components/SubNav.tsx`
- `frontend/src/routes/Guild/index.tsx`
- `frontend/src/routes/Guild/Members.tsx`
- `frontend/src/routes/Guild/Chat.tsx`
- `frontend/src/routes/Guild/Raids.tsx`
- `frontend/src/routes/Friends/index.tsx`
- `frontend/src/routes/Friends/Messages.tsx`
- `frontend/src/routes/Arena.tsx`
- `frontend/src/routes/RaidsTab.tsx`
- `frontend/src/routes/Daily.tsx`
- `frontend/src/routes/Story.tsx`
- `frontend/src/routes/Achievements.tsx`
- `frontend/src/routes/Event.tsx`
- `frontend/src/routes/Crafting.tsx`
- `frontend/src/routes/Account.tsx`

**Modify:**
- `frontend/src/App.tsx` — replace stubs with real route components

---

### Task 1: SubNav component + Guild tab (4 sub-routes)

**Files:**
- Create: `frontend/src/components/SubNav.tsx`
- Create: `frontend/src/api/guild.ts`
- Create: `frontend/src/hooks/useGuild.ts`
- Create: `frontend/src/routes/Guild/index.tsx`
- Create: `frontend/src/routes/Guild/Members.tsx`
- Create: `frontend/src/routes/Guild/Chat.tsx`
- Create: `frontend/src/routes/Guild/Raids.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create SubNav component**

```tsx
// frontend/src/components/SubNav.tsx
import { NavLink } from 'react-router-dom'

interface Tab { path: string; label: string }
interface Props { tabs: Tab[] }

export function SubNav({ tabs }: Props) {
  return (
    <div style={{
      display: 'flex', gap: 2, borderBottom: '1px solid var(--border)',
      marginBottom: 16, overflowX: 'auto',
    }}>
      {tabs.map((t) => (
        <NavLink
          key={t.path}
          to={t.path}
          end
          style={({ isActive }) => ({
            padding: '6px 14px', fontSize: 13, fontWeight: isActive ? 700 : 400,
            color: isActive ? 'var(--text)' : 'var(--muted)',
            borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
            textDecoration: 'none', background: 'transparent', whiteSpace: 'nowrap',
          })}
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create guild API + hook**

```typescript
// frontend/src/api/guild.ts
import type { Guild, GuildMember } from '../types'
import { apiFetch, apiPost, apiDelete } from './client'

export interface GuildMessage { id: number; author_name: string; body: string; created_at: string }
export interface GuildApplication { id: number; applicant_name: string; message: string }

export const fetchMyGuild = (): Promise<{ guild: Guild | null; my_role: string | null }> =>
  apiFetch('/guilds/mine')
export const fetchAllGuilds = (): Promise<Guild[]> => apiFetch('/guilds')
export const fetchGuildMessages = (id: number): Promise<GuildMessage[]> =>
  apiFetch(`/guilds/${id}/messages?limit=20`)
export const fetchGuildApplications = (id: number): Promise<GuildApplication[]> =>
  apiFetch(`/guilds/${id}/applications`)
export const sendGuildMessage = (id: number, body: string) =>
  apiPost(`/guilds/${id}/messages`, { body })
export const applyToGuild = (id: number, message: string) =>
  apiPost(`/guilds/${id}/apply`, { message })
export const createGuild = (name: string, tag: string, description: string) =>
  apiPost('/guilds', { name, tag, description })
export const leaveGuild = (id: number) => apiPost(`/guilds/${id}/leave`, {})
export const acceptApplication = (appId: number) =>
  apiPost(`/guilds/applications/${appId}/accept`, {})
export const rejectApplication = (appId: number) =>
  apiPost(`/guilds/applications/${appId}/reject`, {})
```

```typescript
// frontend/src/hooks/useGuild.ts
import { useQuery } from '@tanstack/react-query'
import { fetchMyGuild } from '../api/guild'
import { useAuthStore } from '../store/auth'

export function useGuild() {
  const jwt = useAuthStore((s) => s.jwt)
  return useQuery({
    queryKey: ['guild'],
    queryFn: fetchMyGuild,
    refetchOnWindowFocus: true,
    enabled: !!jwt,
  })
}
```

- [ ] **Step 3: Create Guild layout route (parent with SubNav)**

```tsx
// frontend/src/routes/Guild/index.tsx
import { Outlet, useNavigate } from 'react-router-dom'
import { SubNav } from '../../components/SubNav'
import { useGuild } from '../../hooks/useGuild'
import { SkeletonGrid } from '../../components/SkeletonGrid'
import { useQueryClient } from '@tanstack/react-query'
import { applyToGuild, createGuild } from '../../api/guild'
import { toast } from '../../store/ui'
import { useState } from 'react'

export function GuildRoute() {
  const { data, isLoading } = useGuild()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [applying, setApplying] = useState<number | null>(null)

  if (isLoading) return <SkeletonGrid count={3} height={80} />

  // Not in a guild — show join/create UI
  if (!data?.guild) {
    return <GuildJoinCreate
      onJoined={() => { qc.invalidateQueries({ queryKey: ['guild'] }) }}
    />
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

function GuildJoinCreate({ onJoined }: { onJoined: () => void }) {
  const { data } = useQuery({ queryKey: ['guilds-all'], queryFn: () => import('../../api/guild').then(m => m.fetchAllGuilds()) })
  const [newName, setNewName] = useState('')
  const [newTag, setNewTag] = useState('')
  const [creating, setCreating] = useState(false)

  async function doCreate() {
    setCreating(true)
    try {
      await createGuild(newName, newTag, '')
      toast.success(`Guild [${newTag}] created!`)
      onJoined()
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
      {data && data.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Join a Guild</h3>
          <div className="stack" style={{ gap: 6 }}>
            {data.map(g => (
              <div key={g.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <span style={{ fontWeight: 700 }}>[{g.tag}] {g.name}</span>
                  <span className="muted" style={{ fontSize: 11, marginLeft: 8 }}>{g.member_count} members</span>
                </div>
                <button style={{ fontSize: 12 }} onClick={async () => {
                  try {
                    await applyToGuild(g.id, '')
                    toast.success('Application sent!')
                    onJoined()
                  } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>
                  Apply
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Need useQuery in GuildJoinCreate — add import
import { useQuery } from '@tanstack/react-query'
```

- [ ] **Step 4: Create Guild overview (index child route)**

```tsx
// frontend/src/routes/Guild/Overview.tsx — rename this as the index content
// Actually rendered directly in the layout when path is exactly /app/guild
// Add as a separate index component imported in App.tsx:

// We'll add it as inline content rendered by GuildRoute when on the index path.
// Create src/routes/Guild/Overview.tsx:
import { useGuild } from '../../hooks/useGuild'
import { useQueryClient } from '@tanstack/react-query'
import { leaveGuild } from '../../api/guild'
import { toast } from '../../store/ui'

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
            }}>
            Leave Guild
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create Guild Members**

```tsx
// frontend/src/routes/Guild/Members.tsx
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
```

- [ ] **Step 6: Create Guild Chat**

```tsx
// frontend/src/routes/Guild/Chat.tsx
import { useGuild } from '../../hooks/useGuild'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchGuildMessages, sendGuildMessage } from '../../api/guild'
import { toast } from '../../store/ui'
import { useState, useRef, useEffect } from 'react'
import { EmptyState } from '../../components/EmptyState'

export function GuildChat() {
  const { data: guildData } = useGuild()
  const guild = guildData?.guild
  const qc = useQueryClient()
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: messages } = useQuery({
    queryKey: ['guild-messages', guild?.id],
    queryFn: () => fetchGuildMessages(guild!.id),
    enabled: !!guild,
    refetchInterval: 10_000,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages?.length])

  if (!guild) return <EmptyState icon="💬" message="Join a guild to chat." />

  async function send() {
    if (!body.trim() || !guild) return
    setSending(true)
    try {
      await sendGuildMessage(guild.id, body.trim())
      setBody('')
      qc.invalidateQueries({ queryKey: ['guild-messages', guild.id] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSending(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 220px)', minHeight: 300 }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {!messages?.length
          ? <EmptyState icon="💬" message="No messages yet." hint="Be the first to say something." />
          : messages.map((m) => (
            <div key={m.id} style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--panel)' }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 600, fontSize: 12 }}>{m.author_name}</span>
                <span className="muted" style={{ fontSize: 10 }}>{new Date(m.created_at).toLocaleTimeString()}</span>
              </div>
              <div style={{ fontSize: 13, marginTop: 2 }}>{m.body}</div>
            </div>
          ))
        }
        <div ref={bottomRef} />
      </div>
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Message your guild…"
          style={{ flex: 1 }}
        />
        <button className="primary" onClick={send} disabled={sending || !body.trim()}>
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Create Guild Raids sub-tab**

```tsx
// frontend/src/routes/Guild/Raids.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiPost } from '../../api/client'
import { useGuild } from '../../hooks/useGuild'
import { useNavigate } from 'react-router-dom'
import { toast } from '../../store/ui'
import { EmptyState } from '../../components/EmptyState'
import type { Raid } from '../../types'

export function GuildRaids() {
  const { data: guildData } = useGuild()
  const guild = guildData?.guild
  const navigate = useNavigate()
  const qc = useQueryClient()

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
```

- [ ] **Step 8: Wire Guild routes in App.tsx**

Replace the guild children:
```tsx
{ path: 'guild', children: [
  { index: true, element: <Stub name="Guild" /> },
  { path: 'members', element: <Stub name="Guild Members" /> },
  { path: 'chat', element: <Stub name="Guild Chat" /> },
  { path: 'raids', element: <Stub name="Guild Raids" /> },
]},
```
with:
```tsx
{ path: 'guild', element: <GuildRoute />, children: [
  { index: true, element: <GuildOverview /> },
  { path: 'members', element: <GuildMembers /> },
  { path: 'chat', element: <GuildChat /> },
  { path: 'raids', element: <GuildRaids /> },
]},
```
Add imports:
```tsx
import { GuildRoute, GuildOverview } from './routes/Guild'
import { GuildMembers } from './routes/Guild/Members'
import { GuildChat } from './routes/Guild/Chat'
import { GuildRaids } from './routes/Guild/Raids'
```

- [ ] **Step 9: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Guild tab with Overview/Members/Chat/Raids sub-routes"
```

---

### Task 2: Friends tab (with DMs sub-route)

**Files:**
- Create: `frontend/src/api/friends.ts`
- Create: `frontend/src/routes/Friends/index.tsx`
- Create: `frontend/src/routes/Friends/Messages.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create friends API**

```typescript
// frontend/src/api/friends.ts
import { apiFetch, apiPost } from './client'

export interface Friend { id: number; name: string; arena_rating: number; status: string }
export interface DmThread { account_id: number; name: string; last_message: string; unread: number; last_at: string }
export interface DmMessage { id: number; sender_id: number; body: string; created_at: string; deleted: boolean }

export const fetchFriends = (): Promise<Friend[]> => apiFetch('/friends')
export const searchUsers = (q: string): Promise<Friend[]> => apiFetch(`/friends/search?q=${encodeURIComponent(q)}`)
export const sendFriendRequest = (id: number) => apiPost(`/friends/${id}/request`, {})
export const fetchDmThreads = (): Promise<DmThread[]> => apiFetch('/dm/threads')
export const fetchDms = (id: number): Promise<DmMessage[]> => apiFetch(`/dm/with/${id}`)
export const sendDm = (id: number, body: string) => apiPost(`/dm/${id}`, { body })
```

- [ ] **Step 2: Create Friends layout route**

```tsx
// frontend/src/routes/Friends/index.tsx
import { Outlet } from 'react-router-dom'
import { SubNav } from '../../components/SubNav'
import { useQuery } from '@tanstack/react-query'
import { fetchFriends, searchUsers, sendFriendRequest } from '../../api/friends'
import { toast } from '../../store/ui'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { EmptyState } from '../../components/EmptyState'

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
  const [results, setResults] = useState<Awaited<ReturnType<typeof searchUsers>>>([])
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
      {/* Search */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add Friend</h3>
        <div className="row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder="Search by username…"
            style={{ flex: 1 }}
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
      {/* Friends list */}
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
```

- [ ] **Step 3: Create Messages sub-route**

```tsx
// frontend/src/routes/Friends/Messages.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDmThreads, fetchDms, sendDm } from '../../api/friends'
import { EmptyState } from '../../components/EmptyState'
import { toast } from '../../store/ui'
import { useState } from 'react'

export function MessagesRoute() {
  const qc = useQueryClient()
  const { data: threads } = useQuery({ queryKey: ['dm-threads'], queryFn: fetchDmThreads, refetchInterval: 15_000 })
  const [activeId, setActiveId] = useState<number | null>(null)
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)

  const { data: messages } = useQuery({
    queryKey: ['dm', activeId],
    queryFn: () => fetchDms(activeId!),
    enabled: !!activeId,
    refetchInterval: 8_000,
  })

  if (!threads?.length) return <EmptyState icon="💬" message="No conversations yet." hint="Send a message from the Friends list." />

  async function send() {
    if (!body.trim() || !activeId) return
    setSending(true)
    try {
      await sendDm(activeId, body.trim())
      setBody('')
      qc.invalidateQueries({ queryKey: ['dm', activeId] })
      qc.invalidateQueries({ queryKey: ['dm-threads'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSending(false) }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 12, height: 'calc(100vh - 220px)', minHeight: 300 }}>
      {/* Thread list */}
      <div style={{ borderRight: '1px solid var(--border)', overflowY: 'auto', paddingRight: 8 }}>
        {threads.map((t) => (
          <div key={t.account_id}
            onClick={() => setActiveId(t.account_id)}
            style={{
              padding: '8px 10px', borderRadius: 6, cursor: 'pointer', marginBottom: 4,
              background: activeId === t.account_id ? 'rgba(78,161,255,0.1)' : 'transparent',
              borderLeft: activeId === t.account_id ? '2px solid var(--accent)' : '2px solid transparent',
            }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{t.name}</div>
            <div className="muted" style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.last_message}</div>
          </div>
        ))}
      </div>
      {/* Message view */}
      {activeId
        ? (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {messages?.filter((m) => !m.deleted).map((m) => (
                <div key={m.id} style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--panel)', alignSelf: 'flex-start', maxWidth: '75%' }}>
                  <div style={{ fontSize: 13 }}>{m.body}</div>
                  <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>{new Date(m.created_at).toLocaleTimeString()}</div>
                </div>
              ))}
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <input value={body} onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()}
                placeholder="Message…" style={{ flex: 1 }} />
              <button className="primary" onClick={send} disabled={sending || !body.trim()}>
                {sending ? '…' : 'Send'}
              </button>
            </div>
          </div>
        )
        : <EmptyState icon="💬" message="Select a conversation." />
      }
    </div>
  )
}
```

- [ ] **Step 4: Wire Friends routes in App.tsx**

Replace:
```tsx
{ path: 'friends', children: [
  { index: true, element: <Stub name="Friends" /> },
  { path: 'messages', element: <Stub name="Messages" /> },
]},
```
with:
```tsx
{ path: 'friends', element: <FriendsLayout />, children: [
  { index: true, element: <FriendsList /> },
  { path: 'messages', element: <MessagesRoute /> },
]},
```
Add imports:
```tsx
import { FriendsLayout, FriendsList } from './routes/Friends'
import { MessagesRoute } from './routes/Friends/Messages'
```

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Friends tab with search + DM threads + Messages sub-route"
```

---

### Task 3: Arena tab

**Files:**
- Create: `frontend/src/api/arena.ts`
- Create: `frontend/src/routes/Arena.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create arena API**

```typescript
// frontend/src/api/arena.ts
import { apiFetch, apiPost } from './client'

export interface ArenaOpponent { account_id: number; name: string; defense_power: number; arena_rating: number }
export interface ArenaLeaderEntry { account_id: number; name: string; arena_rating: number; wins: number; losses: number }
export interface ArenaMatch { id: number; outcome: string; rating_delta: number; created_at: string; role: string; opponent_name: string }

export const fetchArena = (): Promise<{ opponents: ArenaOpponent[]; leaderboard: ArenaLeaderEntry[]; recent: ArenaMatch[] }> =>
  apiFetch('/arena')
export const attackArena = (defender_id: number, hero_ids: number[]) =>
  apiPost<{ outcome: string; rating_delta: number; battle_id: number }>('/arena/attack', { defender_id, hero_ids })
```

- [ ] **Step 2: Create Arena route**

```tsx
// frontend/src/routes/Arena.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchArena, attackArena } from '../api/arena'
import { useNavigate } from 'react-router-dom'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { useState } from 'react'

export function ArenaRoute() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({ queryKey: ['arena'], queryFn: fetchArena })
  const [attacking, setAttacking] = useState<number | null>(null)

  if (isLoading) return <SkeletonGrid />

  async function attack(defenderId: number) {
    setAttacking(defenderId)
    try {
      const res = await attackArena(defenderId, [])
      toast.success(`${res.outcome === 'WIN' ? '⚔️ Victory' : '💀 Defeat'}! Rating ${res.rating_delta >= 0 ? '+' : ''}${res.rating_delta}`)
      qc.invalidateQueries({ queryKey: ['arena'] })
      qc.invalidateQueries({ queryKey: ['me'] })
      navigate(`/battle/${res.battle_id}/replay`)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Attack failed') }
    finally { setAttacking(null) }
  }

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Arena</h2>

      {/* Opponents */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Available Opponents</h3>
        {!data?.opponents?.length
          ? <EmptyState icon="⚔️" message="No opponents available." />
          : data.opponents.map((o) => (
            <div key={o.account_id} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>{o.name}</span>
                <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>⚡ {o.defense_power} · ⚔️ {o.arena_rating}</span>
              </div>
              <button className="primary" style={{ fontSize: 12 }}
                disabled={!!attacking} onClick={() => attack(o.account_id)}>
                {attacking === o.account_id ? '…' : 'Attack'}
              </button>
            </div>
          ))
        }
      </div>

      {/* Leaderboard */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Leaderboard</h3>
        {data?.leaderboard?.map((e, i) => (
          <div key={e.account_id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
            <span><span className="muted" style={{ marginRight: 8 }}>#{i + 1}</span>{e.name}</span>
            <span className="muted">{e.arena_rating} · {e.wins}W {e.losses}L</span>
          </div>
        ))}
      </div>

      {/* Recent matches */}
      {data?.recent?.length ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recent Matches</h3>
          {data.recent.map((m) => (
            <div key={m.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', fontSize: 12, borderBottom: '1px solid var(--border)' }}>
              <span style={{ color: m.outcome === 'WIN' ? 'var(--good)' : 'var(--bad)' }}>{m.outcome}</span>
              <span className="muted">vs {m.opponent_name}</span>
              <span style={{ color: m.rating_delta >= 0 ? 'var(--good)' : 'var(--bad)' }}>
                {m.rating_delta >= 0 ? '+' : ''}{m.rating_delta}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 3: Wire in App.tsx + commit**

```tsx
{ path: 'arena', element: <ArenaRoute /> },
```
```bash
cd .. && git add frontend/src/ && git commit -m "feat: add Arena tab with opponents, leaderboard, recent matches"
```

---

### Task 4: Raids tab, Daily tab, Story tab

**Files:**
- Create: `frontend/src/api/raids.ts`
- Create: `frontend/src/api/daily.ts`
- Create: `frontend/src/api/story.ts`
- Create: `frontend/src/routes/RaidsTab.tsx`
- Create: `frontend/src/routes/Daily.tsx`
- Create: `frontend/src/routes/Story.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create Raids API + hook**

```typescript
// frontend/src/api/raids.ts
import type { Raid } from '../types'
import { apiFetch } from './client'

export interface RaidLeaderEntry { account_id: number; name: string; total_damage: number }

export const fetchMyRaid = (): Promise<Raid | null> => apiFetch('/raids/mine')
export const fetchRaidLeaderboard = (): Promise<RaidLeaderEntry[]> =>
  apiFetch('/raids/leaderboard?days=7&limit=25')
```

```typescript
// frontend/src/hooks/useRaid.ts
import { useQuery } from '@tanstack/react-query'
import { fetchMyRaid } from '../api/raids'
import { useAuthStore } from '../store/auth'

export function useRaid() {
  const jwt = useAuthStore((s) => s.jwt)
  return useQuery({
    queryKey: ['raid'],
    queryFn: fetchMyRaid,
    refetchInterval: 30_000,
    enabled: !!jwt,
  })
}
```

- [ ] **Step 2: Create RaidsTab route**

```tsx
// frontend/src/routes/RaidsTab.tsx
import { useRaid } from '../hooks/useRaid'
import { useQuery } from '@tanstack/react-query'
import { fetchRaidLeaderboard } from '../api/raids'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function RaidsTabRoute() {
  const { data: raid, isLoading } = useRaid()
  const navigate = useNavigate()
  const { data: leaderboard } = useQuery({ queryKey: ['raid-leaderboard'], queryFn: fetchRaidLeaderboard })

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
    </div>
  )
}
```

- [ ] **Step 3: Create Daily API + route**

```typescript
// frontend/src/api/daily.ts
import { apiFetch, apiPost } from './client'

export interface DailyQuest {
  id: number; kind: string; status: string; target_key: string
  goal: number; progress: number; reward_coins: number; reward_gems: number; reward_shards: number
}
export const fetchDaily = (): Promise<{ quests: DailyQuest[] }> => apiFetch('/daily')
export const claimQuest = (id: number) => apiPost(`/daily/${id}/claim`, {})
```

```tsx
// frontend/src/routes/Daily.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDaily, claimQuest } from '../api/daily'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function DailyRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily })
  const quests = data?.quests ?? []

  if (isLoading) return <SkeletonGrid count={4} height={70} />
  if (!quests.length) return <EmptyState icon="📋" message="Daily quests reset at midnight UTC." />

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Daily Quests</h2>
      {quests.map((q) => (
        <div key={q.id} className="card" style={{ padding: '12px 14px' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{q.kind.replace(/_/g, ' ')}</div>
              <div style={{ marginTop: 4 }}>
                <div style={{ background: 'var(--bg-inset)', borderRadius: 3, height: 6, width: 180, overflow: 'hidden' }}>
                  <div style={{ height: '100%', background: q.status === 'COMPLETE' ? 'var(--good)' : 'var(--accent)', width: `${Math.min(100, (q.progress / q.goal) * 100)}%` }} />
                </div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{q.progress}/{q.goal}</div>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: 'var(--warn)', marginBottom: 6 }}>
                {q.reward_coins > 0 && `🪙 ${q.reward_coins} `}
                {q.reward_gems > 0 && `💎 ${q.reward_gems} `}
                {q.reward_shards > 0 && `✦ ${q.reward_shards}`}
              </div>
              {q.status === 'COMPLETE' && (
                <button className="primary" style={{ fontSize: 12 }}
                  onClick={async () => {
                    try { await claimQuest(q.id); toast.success('Claimed!'); qc.invalidateQueries({ queryKey: ['daily'] }); qc.invalidateQueries({ queryKey: ['me'] }) }
                    catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                  }}>
                  Claim
                </button>
              )}
              {q.status === 'CLAIMED' && <span className="muted" style={{ fontSize: 12 }}>✓ Claimed</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Create Story API + route**

```typescript
// frontend/src/api/story.ts
import { apiFetch, apiPost } from './client'

export interface ChapterStatus {
  chapter: number; title: string; completed: boolean; reward_claimed: boolean; stage_count: number; cleared_count: number
}
export const fetchStory = (): Promise<{ account_level: number; account_xp: number; chapters: ChapterStatus[] }> =>
  apiFetch('/story')
export const markCutsceneSeen = (key: string) => apiPost('/story/cutscene-seen', { key })
```

```tsx
// frontend/src/routes/Story.tsx
import { useQuery } from '@tanstack/react-query'
import { fetchStory } from '../api/story'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function StoryRoute() {
  const { data, isLoading } = useQuery({ queryKey: ['story'], queryFn: fetchStory })

  if (isLoading) return <SkeletonGrid count={3} height={80} />
  if (!data) return <EmptyState icon="📖" message="Story unavailable." />

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>📖 Story</h2>
      <div className="card">
        <div style={{ fontSize: 13 }}>Account Level <strong>{data.account_level}</strong></div>
        <div style={{ background: 'var(--bg-inset)', height: 6, borderRadius: 3, marginTop: 6 }}>
          <div style={{ height: '100%', background: 'var(--accent)', borderRadius: 3, width: `${Math.min(100, (data.account_xp % 100))}%` }} />
        </div>
      </div>
      {data.chapters.map((ch) => (
        <div key={ch.chapter} className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 700 }}>{ch.title}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {ch.cleared_count}/{ch.stage_count} stages cleared
                {ch.completed && !ch.reward_claimed && ' · 🎁 Reward available!'}
                {ch.reward_claimed && ' · ✅ Reward claimed'}
              </div>
            </div>
            <span style={{ color: ch.completed ? 'var(--good)' : 'var(--muted)', fontSize: 20 }}>
              {ch.completed ? '✅' : '🔒'}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 5: Wire in App.tsx + commit**

```tsx
import { RaidsTabRoute } from './routes/RaidsTab'
import { DailyRoute } from './routes/Daily'
import { StoryRoute } from './routes/Story'
// ...
{ path: 'raids', element: <RaidsTabRoute /> },
{ path: 'daily', element: <DailyRoute /> },
{ path: 'story', element: <StoryRoute /> },
```

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Raids, Daily, Story tabs"
```

---

### Task 5: Achievements, Event, Crafting, Account tabs

**Files:**
- Create: `frontend/src/api/achievements.ts`
- Create: `frontend/src/api/events.ts`
- Create: `frontend/src/api/crafting.ts`
- Create: `frontend/src/api/account.ts`
- Create: `frontend/src/routes/Achievements.tsx`
- Create: `frontend/src/routes/Event.tsx`
- Create: `frontend/src/routes/Crafting.tsx`
- Create: `frontend/src/routes/Account.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create APIs**

```typescript
// frontend/src/api/achievements.ts
import { apiFetch } from './client'
export interface Achievement { code: string; title: string; description: string; unlocked: boolean; progress: number; goal: number }
export const fetchAchievements = (): Promise<{ items: Achievement[]; unlocked: number; total: number }> =>
  apiFetch('/achievements')
```

```typescript
// frontend/src/api/events.ts
import { apiFetch, apiPost } from './client'
export interface EventQuest { code: string; title: string; goal: number; progress: number; currency_reward: number; completed: boolean; claimed: boolean }
export interface EventMilestone { idx: number; title: string; cost: number; contents: Record<string,number>; redeemed: boolean; affordable: boolean }
export interface ActiveEvent { id: string; display_name: string; currency_name: string; currency_emoji: string; currency_balance: number; ends_at: string; quests: EventQuest[]; milestones: EventMilestone[] }
export const fetchActiveEvent = (): Promise<ActiveEvent | null> => apiFetch('/events/active')
export const claimEventQuest = (eventId: string, questCode: string) => apiPost(`/events/${eventId}/quests/${questCode}/claim`, {})
export const redeemMilestone = (eventId: string, idx: number) => apiPost(`/events/${eventId}/milestones/${idx}/redeem`, {})
```

```typescript
// frontend/src/api/crafting.ts
import { apiFetch, apiPost } from './client'
export interface Material { code: string; name: string; rarity: string; description: string; icon: string; quantity: number }
export interface Recipe { id: number; name: string; description: string; materials: Record<string,number>; coin_cost: number; gem_cost: number; craftable: boolean; blocking_reason: string | null }
export const fetchCrafting = (): Promise<{ materials: Material[]; recipes: Recipe[] }> => apiFetch('/crafting')
export const craftRecipe = (id: number) => apiPost(`/crafting/${id}/craft`, {})
```

```typescript
// frontend/src/api/account.ts
import { apiFetch, apiPost } from './client'
export interface Session { id: number; created_at: string; last_used: string; ip_address: string; is_current: boolean }
export const fetchSessions = (): Promise<Session[]> => apiFetch('/me/sessions')
export const revokeSession = (id: number) => apiPost(`/me/sessions/${id}/revoke`, {})
export const revokeAllSessions = () => apiPost('/me/sessions/revoke-all', {})
export const requestDataExport = () => apiFetch<{ download_url: string }>('/me/export')
export const deleteAccount = () => apiPost('/me/delete', {})
```

- [ ] **Step 2: Create Achievements route**

```tsx
// frontend/src/routes/Achievements.tsx
import { useQuery } from '@tanstack/react-query'
import { fetchAchievements } from '../api/achievements'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'

export function AchievementsRoute() {
  const { data, isLoading } = useQuery({ queryKey: ['achievements'], queryFn: fetchAchievements })

  if (isLoading) return <SkeletonGrid />
  if (!data) return <EmptyState icon="🏆" message="Achievements unavailable." />

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>🏆 Achievements</h2>
        <span className="muted" style={{ fontSize: 12 }}>{data.unlocked}/{data.total} unlocked</span>
      </div>
      {data.items.map((a) => (
        <div key={a.code} className="card" style={{ padding: '12px 14px', opacity: a.unlocked ? 1 : 0.6 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13 }}>{a.unlocked ? '✅ ' : ''}{a.title}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{a.description}</div>
            </div>
            {!a.unlocked && a.goal > 1 && (
              <div style={{ textAlign: 'right', minWidth: 60 }}>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{a.progress}/{a.goal}</div>
                <div style={{ background: 'var(--bg-inset)', height: 4, borderRadius: 2, marginTop: 3, width: 60 }}>
                  <div style={{ height: '100%', background: 'var(--accent)', borderRadius: 2, width: `${Math.min(100, (a.progress / a.goal) * 100)}%` }} />
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Create Event route**

```tsx
// frontend/src/routes/Event.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchActiveEvent, claimEventQuest, redeemMilestone } from '../api/events'
import { toast } from '../store/ui'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function EventRoute() {
  const qc = useQueryClient()
  const { data: event, isLoading } = useQuery({
    queryKey: ['active-event-detail'],
    queryFn: fetchActiveEvent,
    refetchInterval: 60_000,
  })

  if (isLoading) return <SkeletonGrid count={3} height={80} />
  if (!event) return <EmptyState icon="⚡" message="No active event." hint="Events run during special periods." />

  const endsIn = Math.max(0, Math.floor((new Date(event.ends_at).getTime() - Date.now()) / 1000 / 3600))

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>⚡ {event.display_name}</h2>
        <span className="muted" style={{ fontSize: 12 }}>Ends in ~{endsIn}h · {event.currency_emoji} {event.currency_balance}</span>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Quests</h3>
        {event.quests.map((q) => (
          <div key={q.code} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{q.title}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{q.progress}/{q.goal} · +{q.currency_reward} {event.currency_emoji}</div>
            </div>
            {q.completed && !q.claimed && (
              <button className="primary" style={{ fontSize: 12 }}
                onClick={async () => {
                  try { await claimEventQuest(event.id, q.code); toast.success('Claimed!'); qc.invalidateQueries({ queryKey: ['active-event-detail'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Claim</button>
            )}
            {q.claimed && <span className="muted" style={{ fontSize: 11 }}>✓</span>}
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Milestones</h3>
        {event.milestones.map((m) => (
          <div key={m.idx} className="row" style={{ justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', opacity: m.redeemed ? 0.5 : 1 }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{m.title}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{m.cost} {event.currency_emoji}</div>
            </div>
            {!m.redeemed && m.affordable && (
              <button className="primary" style={{ fontSize: 12 }}
                onClick={async () => {
                  try { await redeemMilestone(event.id, m.idx); toast.success('Redeemed!'); qc.invalidateQueries({ queryKey: ['active-event-detail'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Redeem</button>
            )}
            {m.redeemed && <span className="muted" style={{ fontSize: 11 }}>✓</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create Crafting route**

```tsx
// frontend/src/routes/Crafting.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCrafting, craftRecipe } from '../api/crafting'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function CraftingRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['crafting'], queryFn: fetchCrafting })

  if (isLoading) return <SkeletonGrid />
  if (!data) return null

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>⚒️ Crafting</h2>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Materials</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {data.materials.filter((m) => m.quantity > 0).map((m) => (
            <div key={m.code} style={{ padding: '4px 10px', background: 'var(--bg-inset)', borderRadius: 6, fontSize: 12 }}>
              {m.icon} {m.name} ×{m.quantity}
            </div>
          ))}
        </div>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        {data.recipes.map((r) => (
          <div key={r.id} className="card" style={{ padding: '12px 14px', opacity: r.craftable ? 1 : 0.6 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>{r.name}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{r.description}</div>
                {!r.craftable && r.blocking_reason && (
                  <div style={{ fontSize: 11, color: 'var(--bad)', marginTop: 2 }}>{r.blocking_reason}</div>
                )}
              </div>
              <button className="primary" style={{ fontSize: 12 }}
                disabled={!r.craftable}
                onClick={async () => {
                  try { await craftRecipe(r.id); toast.success(`${r.name} crafted!`); qc.invalidateQueries({ queryKey: ['crafting'] }); qc.invalidateQueries({ queryKey: ['me'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>
                Craft
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create Account route**

```tsx
// frontend/src/routes/Account.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSessions, revokeSession, revokeAllSessions, requestDataExport, deleteAccount } from '../api/account'
import { useAuthStore } from '../store/auth'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function AccountRoute() {
  const qc = useQueryClient()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const { data: sessions, isLoading } = useQuery({ queryKey: ['sessions'], queryFn: fetchSessions })

  if (isLoading) return <SkeletonGrid count={3} height={60} />

  async function exportData() {
    try {
      const res = await requestDataExport()
      if (res.download_url) window.location.href = res.download_url
      else toast.info('Export queued — check your email.')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Export failed') }
  }

  async function revokeAll() {
    if (!confirm('Sign out of all other devices?')) return
    try {
      await revokeAllSessions()
      toast.success('All other sessions revoked.')
      qc.invalidateQueries({ queryKey: ['sessions'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  async function doDeleteAccount() {
    if (!confirm('Permanently delete your account? This cannot be undone.')) return
    try {
      await deleteAccount()
      clearJwt()
      qc.clear()
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div className="stack" style={{ maxWidth: 600 }}>
      <h2 style={{ margin: 0 }}>⚙️ Account</h2>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Active Sessions</h3>
        {sessions?.map((s) => (
          <div key={s.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
            <div>
              <span>{s.ip_address}</span>
              {s.is_current && <span className="pill good" style={{ marginLeft: 6, fontSize: 10 }}>current</span>}
              <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>{new Date(s.last_used).toLocaleString()}</div>
            </div>
            {!s.is_current && (
              <button style={{ fontSize: 11 }}
                onClick={async () => {
                  try { await revokeSession(s.id); qc.invalidateQueries({ queryKey: ['sessions'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>
                Revoke
              </button>
            )}
          </div>
        ))}
        <button style={{ marginTop: 10, fontSize: 12 }} onClick={revokeAll}>Sign out all other devices</button>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Data & Privacy</h3>
        <button style={{ fontSize: 12 }} onClick={exportData}>Export my data (GDPR)</button>
      </div>

      <div className="card" style={{ border: '1px solid var(--bad)' }}>
        <h3 style={{ marginTop: 0, color: 'var(--bad)' }}>Danger Zone</h3>
        <button style={{ fontSize: 12, color: 'var(--bad)', borderColor: 'var(--bad)' }} onClick={doDeleteAccount}>
          Delete account permanently
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Wire all remaining routes in App.tsx**

```tsx
import { AchievementsRoute } from './routes/Achievements'
import { EventRoute } from './routes/Event'
import { CraftingRoute } from './routes/Crafting'
import { AccountRoute } from './routes/Account'
// replace stubs:
{ path: 'achievements', element: <AchievementsRoute /> },
{ path: 'event', element: <EventRoute /> },
{ path: 'crafting', element: <CraftingRoute /> },
{ path: 'account', element: <AccountRoute /> },
```

- [ ] **Step 7: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add Achievements, Event, Crafting, Account tabs"
```

---

### Task 6: Full test run

- [ ] **Step 1: Run all frontend tests**

```bash
cd frontend && npx vitest run
```
Expected: all tests pass.

- [ ] **Step 2: TypeScript clean**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Python suite unchanged**

```bash
cd .. && pytest -q
```
Expected: 634 passed, 3 skipped.

- [ ] **Step 4: Manual smoke in browser — verify all tabs render**

```bash
cd frontend && npm run dev
```
Navigate to every tab: Guild, Friends, Arena, Raids, Daily, Story, Achievements, Event, Crafting, Account. Each should render content (or appropriate empty state if no data).

- [ ] **Step 5: Final commit**

```bash
cd .. && git add . && git commit -m "feat: SPA Plan 3 complete — all 15 app tabs implemented"
```

---

**Plan 3 complete.** Next: `2026-04-27-spa-p4-battle-cutover.md` — Battle routes + HTMX deletion + FastAPI swap.
