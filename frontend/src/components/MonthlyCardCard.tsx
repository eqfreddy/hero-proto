import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchMonthlyCard,
  purchaseMonthlyCard,
  claimMonthlyCardDrip,
} from '../api/monthlyCard'
import { toast } from '../store/ui'

/** Inline card for the Me/Dashboard route. Shows current status + CTA. */
export function MonthlyCardCard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['monthly-card'],
    queryFn: fetchMonthlyCard,
    refetchInterval: 60_000,
  })
  const [busy, setBusy] = useState(false)

  if (!data) return null

  async function purchase() {
    setBusy(true)
    try {
      const res = await purchaseMonthlyCard()
      if (res.mode === 'stripe' && res.checkout_url) {
        window.location.href = res.checkout_url
        return
      }
      toast.success('Monthly Card active!')
      qc.invalidateQueries({ queryKey: ['monthly-card'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Purchase failed')
    } finally {
      setBusy(false)
    }
  }

  async function claim() {
    setBusy(true)
    try {
      const res = await claimMonthlyCardDrip()
      if (res.granted_gems > 0) toast.success(`💎 +${res.granted_gems} claimed!`)
      else if (res.already_claimed) toast.info('Already claimed today')
      qc.invalidateQueries({ queryKey: ['monthly-card'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Claim failed')
    } finally {
      setBusy(false)
    }
  }

  if (!data.active) {
    return (
      <div className="card" style={{
        padding: 14, borderLeft: '3px solid var(--warn)',
        background: 'linear-gradient(120deg, rgba(255, 187, 51, 0.08), transparent 60%)',
      }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--warn)', letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 700 }}>
              Monthly Card
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
              💎 100 instant + 💎 50/day for 30 days
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              1,600 gems total — best value, stacks if re-purchased.
            </div>
          </div>
          <button className="primary" disabled={busy} onClick={purchase} style={{ minWidth: 120 }}>
            {busy ? '...' : '$4.99'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{
      padding: 14, borderLeft: '3px solid var(--good)',
      background: 'linear-gradient(120deg, rgba(46, 204, 113, 0.08), transparent 60%)',
    }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--good)', letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 700 }}>
            Monthly Card · Active
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
            {data.days_remaining} day{data.days_remaining === 1 ? '' : 's'} remaining · 💎 {data.drip_gems_per_day}/day
          </div>
        </div>
        {data.drip_available_today ? (
          <button className="primary" disabled={busy} onClick={claim} style={{ minWidth: 120 }}>
            {busy ? '...' : `Claim 💎 ${data.drip_gems_per_day}`}
          </button>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>✓ Claimed today</span>
        )}
      </div>
    </div>
  )
}
