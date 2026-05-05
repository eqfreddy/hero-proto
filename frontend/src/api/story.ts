import { apiFetch, apiPost } from './client'

export interface StoryStage {
  code: string
  name: string
  unlocked: boolean
  cleared: boolean
  intro: { speaker: string; text: string; icon: string } | null
  outro: { speaker: string; text: string; icon: string } | null
}

export interface ChapterStatus {
  code: string
  title: string
  blurb: string
  icon: string
  unlock_level: number
  required_alignment: string | null
  unlocked: boolean
  stages: StoryStage[]
  completion_pct: number
  completed: boolean
  reward_claimed: boolean
  end_reward: Record<string, number>
  alignment_hero: string | null
}

export interface StoryResponse {
  account_level: number
  chapters: ChapterStatus[]
}

export const fetchStory = (): Promise<StoryResponse> => apiFetch('/story')

export const markCutsceneSeen = (chapter_code: string, stage_code: string, beat: string) =>
  apiPost('/story/cutscene-seen', { chapter_code, stage_code, beat })

export interface AlignmentChoiceOut {
  faction: string
  alignment_chosen_at: string
}

export const chooseAlignment = (alignment: 'RESISTANCE' | 'CORP_GREED'): Promise<AlignmentChoiceOut> =>
  apiPost('/story/alignment', { alignment })
