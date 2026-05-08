import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAfkStatus, claimAfk } from '../api/afk'
import { toast } from '../store/ui'

/** Idle income loop card. Shown above the fold on the Me dashboard. */
export function AfkCard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['afk'],
    queryFn: fetchAfkStatus,
    refetchInterval: 30_000,
  })
  const [busy, setBusy] = useState(false)

  if (!data) return null

  const fillPct = Math.min(100, (data.hours_accrued / data.hours_max) * 100)
  const ready = data.pending_coins > 0 || data.pending_hero_xp > 0

  async function claim() {
    setBusy(true)
    try {
      const res = await claimAfk()
      const parts: string[] = []
      if (res.coins > 0) parts.push(`🪙 ${res.coins.toLocaleString()}`)
      if (res.hero_xp > 0) parts.push(`✨ ${res.hero_xp.toLocaleString()} hero XP`)
      toast.success(parts.length ? `Banked ${parts.join(' · ')}` : 'Nothing to claim yet')
      qc.invalidateQueries({ queryKey: ['afk'] })
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Claim failed')
    } finally {
      setBusy(false)
    }
  }

  const cap = data.is_at_cap
  return (
    <div className="card" style={{
      padding: 14,
      borderLeft: `3px solid ${cap ? 'var(--warn)' : 'var(--accent)'}`,
      background: cap
        ? 'linear-gradient(120deg, rgba(255, 187, 51, 0.10), transparent 60%)'
        : 'linear-gradient(120deg, rgba(0, 255, 224, 0.06), transparent 60%)',
    }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 11, color: cap ? 'var(--warn)' : 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 700 }}>
            AFK Income {cap && '· Cap reached — claim now'}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>
            🪙 {data.pending_coins.toLocaleString()}
            {data.pending_hero_xp > 0 && <span style={{ marginLeft: 10 }}>✨ {data.pending_hero_xp.toLocaleString()} XP</span>}
          </div>
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
            {data.hours_accrued.toFixed(1)}h / {data.hours_max}h · {data.coins_per_hour.toLocaleString()} c/h
          </div>
          <div style={{ marginTop: 6, background: 'var(--bg-inset)', borderRadius: 4, height: 6, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: `${fillPct}%`,
              background: cap ? 'var(--warn)' : 'var(--accent)',
              transition: 'width 240ms ease',
            }} />
          </div>
        </div>
        <button
          className="primary"
          disabled={busy || !ready}
          onClick={claim}
          style={{ minWidth: 110 }}
          title={ready ? 'Claim accrued rewards' : 'Nothing accrued yet'}
        >
          {busy ? '...' : ready ? 'Claim' : 'Empty'}
        </button>
      </div>
    </div>
  )
}
