import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchVip, claimVipDrip } from '../api/vip'
import { toast } from '../store/ui'

const TIER_COLORS: Record<number, string> = {
  0: '#5a5a5a',
  1: '#cd7f32', // bronze
  2: '#c0c0c0', // silver
  3: '#ffd700', // gold
  4: '#e5e4e2', // platinum
  5: '#b9f2ff', // diamond
  6: '#a8a9ad', // mythril
  7: '#3d3d3d', // obsidian
  8: '#1a1a1a', // onyx
  9: '#9d4edd', // crown
  10: '#ff006e', // apex
}

export function VipCard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['vip'],
    queryFn: fetchVip,
    refetchInterval: 60_000,
  })
  const [busy, setBusy] = useState(false)

  if (!data) return null

  const tierColor = TIER_COLORS[data.level] ?? '#5a5a5a'
  const progressPct = data.next_perks
    ? Math.min(100, Math.max(0, ((data.xp) / (data.xp + data.xp_to_next)) * 100))
    : 100

  async function claim() {
    setBusy(true)
    try {
      const res = await claimVipDrip()
      if (res.granted_gems > 0) toast.success(`💎 +${res.granted_gems} VIP daily!`)
      else if (res.already_claimed) toast.info('Already claimed today')
      qc.invalidateQueries({ queryKey: ['vip'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Claim failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card" style={{
      padding: 14,
      borderLeft: `3px solid ${tierColor}`,
      background: `linear-gradient(120deg, ${tierColor}1a, transparent 60%)`,
    }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div className="row" style={{ alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 11, color: tierColor, letterSpacing: '0.12em',
              textTransform: 'uppercase', fontWeight: 800,
            }}>
              VIP {data.level} · {data.label}
            </span>
            {data.perks.cosmetic_frame && (
              <span style={{
                fontSize: 9, padding: '1px 6px', borderRadius: 8,
                background: tierColor, color: '#0b0d10', fontWeight: 700,
              }}>frame unlocked</span>
            )}
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>
            🪙 {data.perks.afk_cap_hours}h AFK cap
            {data.perks.auto_battle_speed > 1 && <span style={{ marginLeft: 8 }}>⚡ {data.perks.auto_battle_speed}× auto-battle</span>}
            {data.perks.daily_drip_gems > 0 && <span style={{ marginLeft: 8 }}>💎 {data.perks.daily_drip_gems}/day</span>}
          </div>
          {data.next_label && (
            <>
              <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
                Next: <strong style={{ color: 'var(--accent)' }}>{data.next_label}</strong> in {(data.xp_to_next / 100).toFixed(2)} USD
              </div>
              <div style={{ marginTop: 4, background: 'var(--bg-inset)', borderRadius: 4, height: 5, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${progressPct}%`, background: tierColor,
                  transition: 'width 240ms ease',
                }} />
              </div>
            </>
          )}
          {!data.next_label && (
            <div className="muted" style={{ fontSize: 11, marginTop: 6, color: tierColor, fontWeight: 700 }}>
              Max tier reached.
            </div>
          )}
        </div>
        {data.drip_available_today && (
          <button className="primary" disabled={busy} onClick={claim} style={{ minWidth: 110 }}>
            {busy ? '...' : `Claim 💎 ${data.perks.daily_drip_gems}`}
          </button>
        )}
        {!data.drip_available_today && data.perks.daily_drip_gems > 0 && (
          <span className="muted" style={{ fontSize: 12 }}>✓ Claimed today</span>
        )}
      </div>
    </div>
  )
}
