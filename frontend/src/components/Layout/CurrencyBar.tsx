import { useNavigate } from 'react-router-dom'
import { useMe } from '../../hooks/useMe'
import { useAuthStore } from '../../store/auth'

export function CurrencyBar() {
  const jwt = useAuthStore((s) => s.jwt)
  const { data: me } = useMe()
  const navigate = useNavigate()

  if (!jwt) return null

  if (!me) {
    return <div data-testid="currency-bar" style={{ height: 36, background: 'var(--panel)', borderBottom: '1px solid var(--border)' }} />
  }

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'

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
        <span style={{ position: 'relative' }}>⚡ {me.energy}/{me.energy_cap}</span>
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
