import { apiFetch, apiPost } from './client'

export interface DailyQuest {
  id: number; kind: string; status: string; target_key: string
  goal: number; progress: number; reward_coins: number; reward_gems: number; reward_shards: number
}
export const fetchDaily = (): Promise<{ quests: DailyQuest[] }> => apiFetch('/daily')
export const claimQuest = (id: number) => apiPost(`/daily/${id}/claim`, {})
