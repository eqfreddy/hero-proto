import type { Me } from '../../types'
import { useCountdown } from '../../hooks/useCountdown'

interface Props {
  me: Pick<Me, 'arena_tickets' | 'arena_tickets_cap' | 'arena_tickets_next_tick_in'>
}

const ARENA_TICKETS_REGEN_SECONDS = 4 * 3600

export function TicketHeader({ me }: Props) {
  const nextIn = useCountdown(me.arena_tickets_next_tick_in)
  const missing = Math.max(0, me.arena_tickets_cap - me.arena_tickets)
  const fullSeconds = missing === 0
    ? 0
    : me.arena_tickets_next_tick_in + Math.max(0, missing - 1) * ARENA_TICKETS_REGEN_SECONDS
  const fullIn = useCountdown(fullSeconds)
  const atCap = me.arena_tickets >= me.arena_tickets_cap

  return (
    <div style={{
      padding: '10px 14px',
      background: 'var(--bg-card, var(--panel))',
      border: '1px solid var(--border)',
      borderRadius: 8,
      marginBottom: 12,
      fontSize: 13,
    }}>
      <div style={{ fontWeight: 700 }}>
        🎯 Tickets: {me.arena_tickets} / {me.arena_tickets_cap}
      </div>
      {!atCap && (
        <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}>
          Next ticket in {nextIn}
          {missing > 1 && <> · full in {fullIn}</>}
        </div>
      )}
      {atCap && (
        <div style={{ color: 'var(--good)', fontSize: 11, marginTop: 4 }}>
          Tickets full
        </div>
      )}
    </div>
  )
}
