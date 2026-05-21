import { apiFetch, apiPost } from './client'

export interface ArenaOpponent {
  account_id: number
  name: string
  defense_power: number
  arena_rating: number
}

export interface ArenaLeaderEntry {
  account_id: number
  name: string
  arena_rating: number
  wins: number
  losses: number
}

export interface ArenaMatch {
  id: number
  outcome: string
  rating_delta: number
  created_at: string
  role: string
  opponent_name: string
}

export interface ArenaAttackResponse {
  id: number
  outcome: string
  rating_delta: number
  rewards: { coins: number; shards: number; gems: number }
}

export const fetchArena = (): Promise<{ opponents: ArenaOpponent[]; leaderboard: ArenaLeaderEntry[]; recent: ArenaMatch[] }> =>
  Promise.all([
    apiFetch<Array<{
      account_id: number
      name: string
      team_power: number
      arena_rating: number
    }>>('/arena/opponents'),
    apiFetch<Array<{
      account_id: number
      email: string
      arena_rating: number
      arena_wins: number
      arena_losses: number
    }>>('/arena/leaderboard'),
    Promise.resolve([] as ArenaMatch[]),
  ]).then(([opponents, leaderboard, recent]) => ({
    opponents: opponents.map((opponent) => ({
      account_id: opponent.account_id,
      name: opponent.name,
      defense_power: opponent.team_power,
      arena_rating: opponent.arena_rating,
    })),
    leaderboard: leaderboard.map((entry) => ({
      account_id: entry.account_id,
      name: entry.email.split('@')[0],
      arena_rating: entry.arena_rating,
      wins: entry.arena_wins,
      losses: entry.arena_losses,
    })),
    recent,
  }))

export const attackArena = (defender_account_id: number, team: number[]) =>
  apiPost<ArenaAttackResponse>('/arena/attack', { defender_account_id, team })

export const acknowledgeWeeklyRewards = (): Promise<{ acknowledged: number }> =>
  apiPost<{ acknowledged: number }>('/arena/weekly/acknowledge', {})
