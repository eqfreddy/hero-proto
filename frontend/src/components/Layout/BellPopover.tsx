import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import type { Notification } from '../../types'

export function BellButton() {
  const [open, setOpen] = useState(false)
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

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        aria-haspopup="dialog"
        aria-expanded={open}
        style={{ position: 'relative', background: 'transparent', border: '1px solid var(--border)', color: 'var(--muted)', padding: '4px 8px', borderRadius: 4, fontSize: 14 }}>
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -4, right: -4,
            background: 'var(--bad)', color: 'white',
            fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 8, minWidth: 14, textAlign: 'center',
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
          <h3 style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase' }}>Notifications</h3>
          {!listData?.items?.length
            ? <p style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>No notifications yet.</p>
            : listData.items.map((n) => (
              <div key={n.id} style={{
                padding: '8px 10px', borderRadius: 4, marginBottom: 4,
                background: n.read_at ? 'transparent' : 'rgba(78,161,255,0.08)',
                borderLeft: `2px solid ${n.read_at ? 'var(--border)' : 'var(--accent)'}`,
              }}>
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
