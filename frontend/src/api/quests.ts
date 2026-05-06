import { apiFetch, apiPost } from './client'

export interface QuestTask {
  id: string
  label: string
  event: string
  target: number
  current: number
  done: boolean
}

export interface RewardChoice {
  id: string
  label: string
  description: string
}

export interface QuestReward {
  cosmetic_frame: string
  choice: RewardChoice[]
}

export interface ActiveQuest {
  id: number
  quest_id: string
  name: string
  description: string
  tasks: QuestTask[]
  done_count: number
  total_count: number
  completed_at: string | null
  claimed_at: string | null
  claim_choice: string | null
  dismissed: boolean
  reward: QuestReward
}

export const fetchActiveQuests = (): Promise<ActiveQuest[]> =>
  apiFetch<ActiveQuest[]>('/quests/active')

export const claimQuest = (questId: string, choice: 'epic' | 'gems') =>
  apiPost(`/quests/${questId}/claim`, { choice })

export const dismissQuest = (questId: string) =>
  apiPost(`/quests/${questId}/dismiss`, {})
