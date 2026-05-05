import type { Hero } from '../types'
import { apiPost } from './client'

interface SummonOut { hero: Hero; rarity: string; pulled_epic_pity: boolean }
export interface SummonResult { heroes: Hero[] }

export async function pullStandard(count: 1 | 10): Promise<SummonResult> {
  if (count === 1) {
    const out = await apiPost<SummonOut>('/summon/x1', {})
    return { heroes: [out.hero] }
  }
  const outs = await apiPost<SummonOut[]>('/summon/x10', {})
  return { heroes: outs.map((o) => o.hero) }
}
export const pullEventBanner = (count: 1 | 10): Promise<SummonResult> =>
  apiPost('/summon/event-banner', { count })
