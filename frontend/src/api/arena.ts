import { apiFetch, apiPost } from './client'

export interface ArenaOpponent { account_id: number; name: string; defense_power: number; arena_rating: number }
export interface ArenaLeaderEntry { account_id: number; name: string; arena_rating: number; wins: number; losses: number }
export interface ArenaMatch { id: number; outcome: string; rating_delta: number; created_at: string; role: string; opponent_name: string }

export const fetchArena = (): Promise<{ opponents: ArenaOpponent[]; leaderboard: ArenaLeaderEntry[]; recent: ArenaMatch[] }> =>
  Promise.all([
    apiFetch<ArenaOpponent[]>('/arena/opponents'),
    apiFetch<ArenaLeaderEntry[]>('/arena/leaderboard'),
    Promise.resolve([] as ArenaMatch[]),  // recent matches not yet exposed via API
  ]).then(([opponents, leaderboard, recent]) => ({ opponents, leaderboard, recent }))
export const attackArena = (defender_id: number, hero_ids: number[]) =>
  apiPost<{ outcome: string; rating_delta: number; battle_id: number }>('/arena/attack', { defender_id, hero_ids })
