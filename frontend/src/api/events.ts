import { apiFetch, apiPost } from './client'
export interface EventQuest { code: string; title: string; goal: number; progress: number; currency_reward: number; completed: boolean; claimed: boolean }
export interface EventMilestone { idx: number; title: string; cost: number; contents: Record<string,number>; redeemed: boolean; affordable: boolean }
export interface EventBanner { hero_template_code: string; hero_name: string | null; shard_cost: number; per_account_cap: number; owned: number }
export interface EventBundle { sku: string; title: string; description: string; price_cents: number; contents: Record<string,number>; per_account_limit: number; purchased: boolean }
export interface ActiveEvent { id: string; display_name: string; currency_name: string; currency_emoji: string; currency_balance: number; ends_at: string; quests: EventQuest[]; milestones: EventMilestone[]; banner?: EventBanner | null; bundle?: EventBundle | null }
export const fetchActiveEvent = (): Promise<ActiveEvent | null> => apiFetch('/events/active')
export const claimEventQuest = (eventId: string, questCode: string) => apiPost(`/events/${eventId}/quests/${questCode}/claim`, {})
export const redeemMilestone = (eventId: string, idx: number) => apiPost(`/events/${eventId}/milestones/${idx}/redeem`, {})
