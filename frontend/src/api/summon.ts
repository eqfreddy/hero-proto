import type { Hero } from '../types'
import { apiPost } from './client'

export interface SummonPullOutcome {
  hero: Hero
  rarity: string
  pulled_epic_pity: boolean
  pulls_since_epic_after?: number
  is_duplicate?: boolean
  shards_granted?: number
}

export interface SummonResult {
  heroes: Hero[]
  outcomes: SummonPullOutcome[]
}

export async function pullStandard(count: 1 | 10): Promise<SummonResult> {
  if (count === 1) {
    const out = await apiPost<SummonPullOutcome>('/summon/x1', {})
    return { heroes: [out.hero], outcomes: [out] }
  }
  const outs = await apiPost<SummonPullOutcome[]>('/summon/x10', {})
  return { heroes: outs.map((o) => o.hero), outcomes: outs }
}
export const pullEventBanner = (count: 1 | 10): Promise<SummonResult> =>
  apiPost('/summon/event-banner', { count })
