import { apiFetch, apiPost } from './client'

export interface AfkStatus {
  pending_coins: number
  pending_hero_xp: number
  hours_accrued: number
  hours_max: number
  is_at_cap: boolean
  coins_per_hour: number
  hero_xp_per_hour: number
}

export interface AfkClaimResult {
  coins: number
  hero_xp: number
  heroes_xp_grants: { hero_id: number; xp: number }[]
}

export const fetchAfkStatus = (): Promise<AfkStatus> =>
  apiFetch<AfkStatus>('/afk')

export const claimAfk = () =>
  apiPost<AfkClaimResult>('/afk/claim', {})
