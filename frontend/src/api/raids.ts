import type { Raid } from '../types'
import { apiFetch } from './client'

export interface RaidLeaderEntry { account_id: number; name: string; total_damage: number }

export const fetchMyRaid = (): Promise<Raid | null> => apiFetch('/raids/mine')
export const fetchRaidLeaderboard = (): Promise<RaidLeaderEntry[]> =>
  apiFetch('/raids/leaderboard?days=7&limit=25')
