import type { Hero } from '../types'
import { apiFetch, apiPost } from './client'

export const fetchHeroes = (): Promise<Hero[]> => apiFetch<Hero[]>('/heroes')
export const fetchHero = (id: number): Promise<Hero> => apiFetch<Hero>(`/heroes/${id}`)
export const ascendHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/ascend`, {})
export const skillUpHero = (id: number): Promise<Hero> => apiPost(`/heroes/${id}/skill_up`, {})
