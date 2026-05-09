import type { Hero } from '../types'
import { apiFetch, apiPost } from './client'

export const fetchHeroes = (): Promise<Hero[]> => apiFetch<Hero[]>('/heroes/mine')
export const fetchHero = (id: number): Promise<Hero> => apiFetch<Hero>(`/heroes/${id}/preview`)
export const ascendHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/ascend`, {})
export const ascendHeroWithShards = (id: number): Promise<Hero> =>
  apiPost(`/heroes/${id}/ascend-with-shards`, {})
export const fetchTemplateShards = (): Promise<Record<string, number>> =>
  apiFetch<Record<string, number>>('/heroes/template-shards')
export const skillUpHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/skill_up`, {})

export const SHARDS_TO_ASCEND_FROM: Record<number, number> = {
  1: 10, 2: 30, 3: 80, 4: 200, 5: 500,
}
