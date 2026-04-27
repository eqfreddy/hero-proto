import { apiFetch, apiPost } from './client'

export interface ChapterStatus {
  chapter: number; title: string; completed: boolean; reward_claimed: boolean; stage_count: number; cleared_count: number
}
export const fetchStory = (): Promise<{ account_level: number; account_xp: number; chapters: ChapterStatus[] }> =>
  apiFetch('/story')
export const markCutsceneSeen = (key: string) => apiPost('/story/cutscene-seen', { key })
