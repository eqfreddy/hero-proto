import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiPost } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import type { Notification } from '../../types'

async function markRead(id: number) {
  await apiPost(`/notifications/${id}/read`, {})
}
async function markAllRead() {
  await apiPost('/notifications/read-all', {})
}
async function clearAll() {
  await apiFetch('/notifications', { method: 'DELETE' })
}

export function BellButton() {
  const [open, setOpen] = useState(false)
  const qc = useQueryClient()
  const jwt = useAuthStore((s) => s.jwt)

  const { data: countData } = useQuery({
    queryKey: ['notifications', 'count'],
    queryFn: () => apiFetch<{ unread: number }>('/notifications/unread-count'),
    refetchInterval: 30_000,
    enabled: !!jwt,
  })
  const { data: listData } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => apiFetch<{ items: Notification[] }>('/notifications?limit=30'),
    enabled: open && !!jwt,
  })

  const unread = countData?.unread ?? 0
  const items = listData?.items ?? []

  function invalidate() {
    qc.invalidateQueries({ queryKey: ['notifications'] })
    qc.invalidateQueries({ queryKey: ['notifications', 'count'] })
  }

  async function handleMarkRead(id: number) {
    await markRead(id)
    invalidate()
  }

  async function handleMarkAll() {
    await markAllRead()
    invalidate()
  }

  async function handleClearAll() {
    await clearAll()
    invalidate()
  }

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        aria-haspopup="dialog"
        aria-expanded={open}
        className="icon-btn"
        style={{ fontSize: 14 }}
      >
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -2, right: -2,
            background: 'var(--bad)', color: 'white',
            fontSize: 10, fontWeight: 800, padding: '1px 5px', borderRadius: 10, minWidth: 16, textAlign: 'center',
            boxShadow: '0 0 0 2px var(--panel)',
          }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 40, right: 0, zIndex: 100,
          background: 'var(--panel)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 12, minWidth: 320, maxWidth: 400,
          maxHeight: 480, overflowY: 'auto', boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase' }}>Notifications</h3>
            {items.length > 0 && (
              <div style={{ display: 'flex', gap: 6 }}>
                {unread > 0 && (
                  <button onClick={handleMarkAll} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-inset)', border: '1px solid var(--border)', color: 'var(--muted)', cursor: 'pointer' }}>
                    Mark all read
                  </button>
                )}
                <button onClick={handleClearAll} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-inset)', border: '1px solid var(--border)', color: 'var(--bad)', cursor: 'pointer' }}>
                  Clear all
                </button>
              </div>
            )}
          </div>

          {!items.length
            ? <p style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>No notifications yet.</p>
            : items.map((n) => (
              <div
                key={n.id}
                onClick={() => !n.read_at && handleMarkRead(n.id)}
                style={{
                  padding: '8px 10px', borderRadius: 4, marginBottom: 4,
                  background: n.read_at ? 'transparent' : 'rgba(78,161,255,0.08)',
                  borderLeft: `2px solid ${n.read_at ? 'var(--border)' : 'var(--accent)'}`,
                  cursor: n.read_at ? 'default' : 'pointer',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 12 }}>{n.icon ?? '🔔'} {n.title}</div>
                {n.body && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{n.body}</div>}
              </div>
            ))
          }
        </div>
      )}
    </div>
  )
}
