import type { Hero } from '../types'
import { apiFetch, apiPost } from './client'

export const fetchHeroes = (): Promise<Hero[]> => apiFetch<Hero[]>('/heroes/mine')
export const ascendHeroWithShards = (id: number): Promise<Hero> =>
  apiPost(`/heroes/${id}/ascend-with-shards`, {})
export const fetchTemplateShards = (): Promise<Record<string, number>> =>
  apiFetch<Record<string, number>>('/heroes/template-shards')
export const skillUpHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/skill_up`, {})

export const SHARDS_TO_ASCEND_FROM: Record<number, number> = {
  1: 10, 2: 30, 3: 80, 4: 200, 5: 500,
}

// Shard cost to skill_up FROM the given special_level. Mirrors
// app/template_shards.py::SHARDS_TO_SKILL_UP.
export const SHARDS_TO_SKILL_UP: Record<number, number> = {
  1: 5, 2: 15, 3: 40, 4: 100,
}
