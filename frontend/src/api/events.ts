import { apiFetch, apiPost } from './client'
export interface EventQuest { code: string; title: string; goal: number; progress: number; currency_reward: number; completed: boolean; claimed: boolean }
export interface EventMilestone { idx: number; title: string; cost: number; contents: Record<string,number>; redeemed: boolean; affordable: boolean }
export interface ActiveEvent { id: string; display_name: string; currency_name: string; currency_emoji: string; currency_balance: number; ends_at: string; quests: EventQuest[]; milestones: EventMilestone[] }
export const fetchActiveEvent = (): Promise<ActiveEvent | null> => apiFetch('/events/active')
export const claimEventQuest = (eventId: string, questCode: string) => apiPost(`/events/${eventId}/quests/${questCode}/claim`, {})
export const redeemMilestone = (eventId: string, idx: number) => apiPost(`/events/${eventId}/milestones/${idx}/redeem`, {})
