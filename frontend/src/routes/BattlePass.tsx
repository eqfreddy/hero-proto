import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchBattlePass,
  claimBattlePassTier,
  purchaseBattlePassPremium,
  rewardsByTier,
  priceUSD,
  type BPState,
  type BPReward,
} from '../api/battlePass'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { isNative } from '../native'

const KIND_ICON: Record<string, string> = {
  gems: '💎',
  shards: '✦',
  coins: '🪙',
}

function RewardCell({ rewards, claimed, locked, claimable, onClaim, dim }: {
  rewards: BPReward[]
  claimed: boolean
  locked: boolean
  claimable: boolean
  onClaim: () => void
  dim?: boolean
}) {
  if (rewards.length === 0) {
    return (
      <div style={{
        height: 84, border: '1px dashed var(--border)', borderRadius: 6,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: 0.4, fontSize: 11, color: 'var(--muted)',
      }}>—</div>
    )
  }
  const bg = claimed ? 'var(--bg-inset)' : claimable ? 'var(--accent)' : 'var(--panel)'
  const color = claimed ? 'var(--muted)' : claimable ? '#fff' : 'inherit'
  return (
    <button
      disabled={!claimable || locked}
      onClick={onClaim}
      style={{
        height: 84, padding: 6, borderRadius: 6,
        border: '1px solid var(--border)',
        background: bg, color,
        cursor: claimable ? 'pointer' : 'default',
        opacity: dim ? 0.5 : 1,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: 2,
      }}
    >
      {rewards.map((r, i) => (
        <div key={i} style={{ fontSize: 12, fontWeight: 600 }}>
          {KIND_ICON[r.kind] ?? '?'} {r.amount}
        </div>
      ))}
      <div style={{ fontSize: 9, marginTop: 2, opacity: 0.85, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        {claimed ? '✓ claimed' : claimable ? 'claim' : locked ? '🔒 locked' : 'pending'}
      </div>
    </button>
  )
}

export function BattlePassRoute() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['battle-pass'],
    queryFn: fetchBattlePass,
    refetchInterval: 30_000,
  })
  const [claiming, setClaiming] = useState<string | null>(null)
  const [purchasing, setPurchasing] = useState(false)

  const freeByTier = useMemo(
    () => data?.season ? rewardsByTier(data.season.tracks.free) : new Map(),
    [data?.season],
  )
  const premiumByTier = useMemo(
    () => data?.season ? rewardsByTier(data.season.tracks.premium) : new Map(),
    [data?.season],
  )

  if (isLoading) return <SkeletonGrid count={6} height={70} />
  if (!data?.active || !data.season || !data.progress) {
    return <EmptyState icon="🎫" message="No active Battle Pass season right now." />
  }

  const { season, progress } = data
  const claimedFree = new Set(progress.claimed_free)
  const claimedPremium = new Set(progress.claimed_premium)
  const xpInTier = progress.xp_total - progress.current_tier * season.xp_per_tier
  const xpPct = Math.min(100, Math.max(0, (xpInTier / season.xp_per_tier) * 100))
  const seasonEndsAt = season.ends_at ? new Date(season.ends_at) : null
  const daysLeft = seasonEndsAt
    ? Math.max(0, Math.ceil((seasonEndsAt.getTime() - Date.now()) / 86_400_000))
    : null

  async function handleClaim(tier: number, track: 'free' | 'premium') {
    const key = `${tier}-${track}`
    setClaiming(key)
    try {
      const res = await claimBattlePassTier(tier, track)
      if (res.already_claimed) {
        toast.info('Already claimed')
      } else {
        const parts: string[] = []
        if (res.granted.gems) parts.push(`💎 ${res.granted.gems}`)
        if (res.granted.shards) parts.push(`✦ ${res.granted.shards}`)
        if (res.granted.coins) parts.push(`🪙 ${res.granted.coins}`)
        toast.success(parts.length ? `Tier ${tier} — ${parts.join(' · ')}` : `Tier ${tier} claimed`)
      }
      qc.invalidateQueries({ queryKey: ['battle-pass'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Claim failed')
    } finally {
      setClaiming(null)
    }
  }

  async function handlePurchase() {
    setPurchasing(true)
    try {
      const res = await purchaseBattlePassPremium()
      if (res.mode === 'stripe' && res.checkout_url) {
        // Real-money path — redirect to Stripe-hosted checkout. Webhook will
        // complete the Purchase + grant the premium track on success.
        window.location.href = res.checkout_url
        return
      }
      toast.success('Premium track unlocked!')
      qc.invalidateQueries({ queryKey: ['battle-pass'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Purchase failed')
    } finally {
      setPurchasing(false)
    }
  }

  const tiers = Array.from({ length: season.max_tier }, (_, i) => i + 1)

  return (
    <div className="stack" style={{ gap: 16 }}>
      {/* Header */}
      <div className="card" style={{ padding: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Battle Pass
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, marginTop: 2 }}>{season.name}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{season.description}</div>
            {daysLeft !== null && (
              <div style={{ fontSize: 12, color: 'var(--warn)', marginTop: 6 }}>
                ⏳ {daysLeft} day{daysLeft === 1 ? '' : 's'} remaining
              </div>
            )}
          </div>
          {!progress.premium_purchased && !isNative() && (
            <button
              className="primary"
              disabled={purchasing}
              onClick={handlePurchase}
              style={{ minWidth: 160 }}
            >
              {purchasing ? '...' : `Unlock Premium · ${priceUSD(season.premium_price_cents)}`}
            </button>
          )}
          {!progress.premium_purchased && isNative() && (
            <div className="muted" style={{ fontSize: 11, maxWidth: 180, textAlign: 'right' }}>
              Premium unlock available on the web version (heroproto.com).
            </div>
          )}
          {progress.premium_purchased && (
            <div style={{ fontSize: 12, color: 'var(--good)', fontWeight: 700 }}>✓ Premium Unlocked</div>
          )}
        </div>

        {/* XP bar */}
        <div style={{ marginTop: 14 }}>
          <div className="row" style={{ justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
            <span style={{ fontWeight: 600 }}>Tier {progress.current_tier} / {season.max_tier}</span>
            <span className="muted">
              {progress.current_tier >= season.max_tier
                ? `${progress.xp_total.toLocaleString()} XP — MAX`
                : `${xpInTier} / ${season.xp_per_tier} XP to next tier`}
            </span>
          </div>
          <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 10, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${progress.current_tier >= season.max_tier ? 100 : xpPct}%`,
              background: progress.current_tier >= season.max_tier ? 'var(--good)' : 'var(--accent)',
              transition: 'width 240ms ease',
            }} />
          </div>
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
            Earn XP by winning battles, clearing stages, daily quests, arena attacks, and raid contributions.
          </div>
        </div>
      </div>

      {/* Tier ladder */}
      <div className="card" style={{ padding: 14, overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '64px 1fr', gap: 10, minWidth: 600 }}>
          {/* Header row */}
          <div></div>
          <div style={{
            display: 'grid', gridTemplateColumns: `repeat(${season.max_tier}, 80px)`, gap: 6,
          }}>
            {tiers.map((t) => (
              <div key={t} style={{
                fontSize: 11, fontWeight: 600, textAlign: 'center',
                color: t === progress.current_tier ? 'var(--accent)' : 'var(--muted)',
              }}>
                {t}
              </div>
            ))}
          </div>

          {/* Free row */}
          <div style={{ alignSelf: 'center', fontWeight: 600, fontSize: 13, padding: '8px 0' }}>Free</div>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${season.max_tier}, 80px)`, gap: 6 }}>
            {tiers.map((t) => {
              const rewards = freeByTier.get(t) ?? []
              const claimed = claimedFree.has(t)
              const locked = t > progress.current_tier
              const claimable = !claimed && !locked && rewards.length > 0 && claiming !== `${t}-free`
              return (
                <RewardCell
                  key={t}
                  rewards={rewards}
                  claimed={claimed}
                  locked={locked}
                  claimable={claimable}
                  onClaim={() => handleClaim(t, 'free')}
                />
              )
            })}
          </div>

          {/* Premium row */}
          <div style={{ alignSelf: 'center', fontWeight: 600, fontSize: 13, padding: '8px 0', color: progress.premium_purchased ? 'var(--warn)' : 'var(--muted)' }}>
            Premium
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${season.max_tier}, 80px)`, gap: 6 }}>
            {tiers.map((t) => {
              const rewards = premiumByTier.get(t) ?? []
              const claimed = claimedPremium.has(t)
              const locked = t > progress.current_tier
              const claimable = progress.premium_purchased && !claimed && !locked && rewards.length > 0 && claiming !== `${t}-premium`
              return (
                <RewardCell
                  key={t}
                  rewards={rewards}
                  claimed={claimed}
                  locked={locked}
                  claimable={claimable}
                  onClaim={() => handleClaim(t, 'premium')}
                  dim={!progress.premium_purchased}
                />
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// Tiny helper to compute claimable tier count for NavBar badge.
export function claimableTierCount(state: BPState | null | undefined): number {
  if (!state?.active || !state.season || !state.progress) return 0
  const { season, progress } = state
  const claimedFree = new Set(progress.claimed_free)
  const claimedPremium = new Set(progress.claimed_premium)
  let n = 0
  const freeByT = rewardsByTier(season.tracks.free)
  const premiumByT = rewardsByTier(season.tracks.premium)
  for (let t = 1; t <= progress.current_tier; t++) {
    if ((freeByT.get(t) ?? []).length > 0 && !claimedFree.has(t)) n++
    if (progress.premium_purchased && (premiumByT.get(t) ?? []).length > 0 && !claimedPremium.has(t)) n++
  }
  return n
}
