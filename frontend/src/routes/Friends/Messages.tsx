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
      <div style={{ borderRight: '1px solid var(--border)', overflowY: 'auto', paddingRight: 8 }}>
        {threads.map((t) => (
          <div key={t.account_id}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setActiveId(t.account_id) }}
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
                placeholder="Message…" style={{ flex: 1 }}
                aria-label="Direct message" />
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
