import { apiFetch, apiPost } from './client'

export interface MonthlyCardStatus {
  active: boolean
  ends_at: string | null
  days_remaining: number
  drip_available_today: boolean
  drip_gems_per_day: number
}

export interface MonthlyCardPurchaseResult {
  purchased: boolean
  mode: 'mock' | 'stripe'
  ends_at: string | null
  purchase_id: number
  checkout_url: string | null
}

export const fetchMonthlyCard = (): Promise<MonthlyCardStatus> =>
  apiFetch<MonthlyCardStatus>('/monthly-card')

export const purchaseMonthlyCard = () =>
  apiPost<MonthlyCardPurchaseResult>('/monthly-card/purchase', {})

export const claimMonthlyCardDrip = () =>
  apiPost<{ granted_gems: number; already_claimed: boolean; card_active: boolean }>(
    '/monthly-card/claim', {},
  )
