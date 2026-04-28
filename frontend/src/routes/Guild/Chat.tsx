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
          aria-label="Guild message"
        />
        <button className="primary" onClick={send} disabled={sending || !body.trim()}>
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
