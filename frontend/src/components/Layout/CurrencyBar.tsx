import { useNavigate } from 'react-router-dom'
import { useMe } from '../../hooks/useMe'
import { useAuthStore } from '../../store/auth'
import { useCountdown } from '../../hooks/useCountdown'

export function CurrencyBar() {
  const jwt = useAuthStore((s) => s.jwt)
  const { data: me } = useMe()
  const navigate = useNavigate()
  // Hooks MUST run unconditionally on every render — call them before any early
  // return. Pass 0 when data isn't loaded yet; the timer just shows 0:00 until
  // the next /me refetch flushes the real value through.
  const energyTimer = useCountdown(me?.energy_next_tick_in ?? 0)
  const ticketTimer = useCountdown(me?.arena_tickets_next_tick_in ?? 0)

  if (!jwt) return null

  if (!me) {
    return <div data-testid="currency-bar" style={{ height: 36, background: 'var(--panel)', borderBottom: '1px solid var(--border)' }} />
  }

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'
  const showEnergyTimer = me.energy < me.energy_cap
  const ticketsAtCap = me.arena_tickets >= me.arena_tickets_cap

  return (
    <div
      data-testid="currency-bar"
      style={{
        display: 'flex', gap: 6, padding: '6px 14px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(180deg, var(--panel) 0%, var(--bg) 100%)',
        fontSize: 12, flexWrap: 'nowrap', alignItems: 'center',
        overflowX: 'auto', scrollbarWidth: 'none',
      }}
    >
      <button
        className="cb-pill"
        onClick={() => navigate('/app/shop')}
        style={{ color: 'var(--accent)' }}
        title="Buy gems"
      >
        💎 <span>{me.gems.toLocaleString()}</span>
      </button>
      <button
        className="cb-pill"
        onClick={() => navigate('/app/summon')}
        style={{ color: 'var(--r-rare)' }}
        title="Use shards on Summon"
      >
        ✦ <span>{me.shards.toLocaleString()}</span>
      </button>
      <span className="cb-pill" style={{ color: 'var(--warn)' }}>
        🪙 <span>{me.coins.toLocaleString()}</span>
      </span>
      <span className="cb-pill">
        🎫 <span>{me.access_cards.toLocaleString()}</span>
      </span>
      <span
        className="cb-pill"
        style={{
          color: energyColor,
          position: 'relative',
          overflow: 'hidden',
        }}
        title={`${me.energy} of ${me.energy_cap} energy`}
      >
        <span
          aria-hidden="true"
          style={{
            position: 'absolute', inset: 0,
            background: `linear-gradient(90deg, ${energyColor}22 ${energyPct}%, transparent ${energyPct}%)`,
            pointerEvents: 'none',
          }}
        />
        <span style={{ position: 'relative' }}>
          ⚡ {me.energy}/{me.energy_cap}
          {showEnergyTimer && (
            <span style={{ marginLeft: 6, color: 'var(--muted)', fontSize: 10, fontWeight: 400 }}>
              +1 in {energyTimer}
            </span>
          )}
        </span>
      </span>
      <span
        className="cb-pill"
        style={{ color: ticketsAtCap ? 'var(--good)' : 'var(--accent)' }}
        title={`${me.arena_tickets} of ${me.arena_tickets_cap} arena tickets`}
      >
        🎯 {me.arena_tickets}/{me.arena_tickets_cap}
        {!ticketsAtCap && (
          <span style={{ marginLeft: 6, color: 'var(--muted)', fontSize: 10, fontWeight: 400 }}>
            +1 in {ticketTimer}
          </span>
        )}
      </span>
      {me.free_summon_credits > 0 && (
        <span className="cb-pill" style={{ color: 'var(--r-epic)' }}>
          🎟️ <span>{me.free_summon_credits}</span>
        </span>
      )}
      <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span className="muted" style={{ fontSize: 11 }}>Lv</span>
        <span style={{ fontWeight: 800, color: 'var(--accent)' }}>{me.account_level}</span>
      </span>
    </div>
  )
}
