import { apiFetch, apiPost } from './client'

export interface TowerStatus {
  floor: number
  best_floor: number
  attempts_today: number
  attempts_max: number
  attempts_remaining: number
  season_key: string
  next_floor_preview: {
    floor: number
    enemy_count: number
    enemy_level: number
    rewards: { coins?: number; gems?: number; shards?: number }
  }
}

export interface TowerAttemptResult {
  won: boolean
  floor_attempted: number
  floor_after: number
  best_floor: number
  attempts_remaining: number
  rewards: { coins?: number; gems?: number; shards?: number }
  log_summary: { outcome: string; turns: number | null }
}

export interface TowerLeaderRow {
  account_id: number
  best_floor: number
  current_floor: number
}

export const fetchTower = (): Promise<TowerStatus> => apiFetch<TowerStatus>('/tower')
export const attemptTower = (team: number[]) =>
  apiPost<TowerAttemptResult>('/tower/attempt', { team })
export const fetchTowerLeaderboard = (): Promise<TowerLeaderRow[]> =>
  apiFetch<TowerLeaderRow[]>('/tower/leaderboard?limit=25')
