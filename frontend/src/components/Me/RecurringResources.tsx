import type { Me } from '../../types'
import { useCountdown } from '../../hooks/useCountdown'
import { useDailyResetCountdown } from '../../hooks/useDailyResetCountdown'

interface Props {
  me: Me
}

export function RecurringResources({ me }: Props) {
  const energyTimer = useCountdown(me.energy_next_tick_in)
  const ticketTimer = useCountdown(me.arena_tickets_next_tick_in)
  const dailyTimer = useDailyResetCountdown()
  const energyAtCap = me.energy >= me.energy_cap
  const ticketsAtCap = me.arena_tickets >= me.arena_tickets_cap

  const Row = ({ icon, label, value, timer, atCap }: {
    icon: string; label: string; value: string; timer: string; atCap: boolean
  }) => (
    <div style={{
      display: 'flex', alignItems: 'baseline', gap: 8, padding: '6px 0',
      fontSize: 13,
    }}>
      <span style={{ width: 100, color: 'var(--muted)' }}>{icon} {label}</span>
      <span style={{ width: 90, fontWeight: 600 }}>{value}</span>
      <span style={{ color: atCap ? 'var(--good)' : 'var(--muted)', fontSize: 11 }}>
        {atCap ? 'full' : `+1 in ${timer}`}
      </span>
    </div>
  )

  return (
    <div style={{
      padding: 14,
      background: 'var(--bg-card, var(--panel))',
      border: '1px solid var(--border)',
      borderRadius: 8,
      marginTop: 16,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>Recurring Resources</div>
      <Row icon="⚡" label="Energy" value={`${me.energy} / ${me.energy_cap}`}
           timer={energyTimer} atCap={energyAtCap} />
      <Row icon="🎯" label="Arena" value={`${me.arena_tickets} / ${me.arena_tickets_cap}`}
           timer={ticketTimer} atCap={ticketsAtCap} />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '6px 0', fontSize: 13 }}>
        <span style={{ width: 100, color: 'var(--muted)' }}>📅 Daily reset</span>
        <span style={{ width: 90 }}></span>
        <span style={{ color: 'var(--muted)', fontSize: 11 }}>in {dailyTimer}</span>
      </div>
    </div>
  )
}
