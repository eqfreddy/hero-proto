import { apiFetch, apiPost } from './client'

export interface ArenaOpponent { account_id: number; name: string; defense_power: number; arena_rating: number }
export interface ArenaLeaderEntry { account_id: number; name: string; arena_rating: number; wins: number; losses: number }
export interface ArenaMatch { id: number; outcome: string; rating_delta: number; created_at: string; role: string; opponent_name: string }

export const fetchArena = (): Promise<{ opponents: ArenaOpponent[]; leaderboard: ArenaLeaderEntry[]; recent: ArenaMatch[] }> =>
  apiFetch('/arena')
export const attackArena = (defender_id: number, hero_ids: number[]) =>
  apiPost<{ outcome: string; rating_delta: number; battle_id: number }>('/arena/attack', { defender_id, hero_ids })
