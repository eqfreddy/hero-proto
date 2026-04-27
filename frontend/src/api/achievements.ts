import { apiFetch } from './client'
export interface Achievement { code: string; title: string; description: string; unlocked: boolean; progress: number; goal: number }
export const fetchAchievements = (): Promise<{ items: Achievement[]; unlocked: number; total: number }> =>
  apiFetch('/achievements')
