import type { Hero } from '../types'
import { apiPost } from './client'

interface SummonResult { heroes: Hero[] }

export const pullStandard = (count: 1 | 10): Promise<SummonResult> =>
  count === 1 ? apiPost('/summon/x1', {}) : apiPost('/summon/x10', {})
export const pullEventBanner = (count: 1 | 10): Promise<SummonResult> =>
  apiPost('/summon/event-banner', { count })
