import { apiFetch, apiPost } from './client'

export interface BPReward {
  tier: number
  kind: 'gems' | 'shards' | 'coins' | string
  amount: number
}

export interface BPSeason {
  id: number
  code: string
  name: string
  description: string
  starts_at: string | null
  ends_at: string | null
  max_tier: number
  xp_per_tier: number
  premium_price_cents: number
  tracks: { free: BPReward[]; premium: BPReward[] }
}

export interface BPProgress {
  xp_total: number
  current_tier: number
  premium_purchased: boolean
  claimed_free: number[]
  claimed_premium: number[]
}

export interface BPState {
  active: boolean
  season: BPSeason | null
  progress: BPProgress | null
}

export interface BPClaimResult {
  granted: { gems?: number; shards?: number; coins?: number }
  tier: number
  track: 'free' | 'premium'
  already_claimed: boolean
}

export const fetchBattlePass = (): Promise<BPState> =>
  apiFetch<BPState>('/battle-pass')

export const claimBattlePassTier = (tier: number, track: 'free' | 'premium') =>
  apiPost<BPClaimResult>(`/battle-pass/claim/${tier}`, { track })

export interface BPPurchaseResult {
  purchased: boolean
  mode: 'mock' | 'stripe'
  season_code: string
  premium_purchased_at?: string | null
  purchase_id: number
  checkout_url: string | null
}

export const purchaseBattlePassPremium = () =>
  apiPost<BPPurchaseResult>('/battle-pass/purchase-premium', {})

// --- Helpers ---------------------------------------------------------------

export function rewardsByTier(rewards: BPReward[]): Map<number, BPReward[]> {
  const m = new Map<number, BPReward[]>()
  for (const r of rewards) {
    const list = m.get(r.tier) ?? []
    list.push(r)
    m.set(r.tier, list)
  }
  return m
}

export function xpInCurrentTier(xp: number, xpPerTier: number, currentTier: number): number {
  return xp - currentTier * xpPerTier
}

export function priceUSD(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}
