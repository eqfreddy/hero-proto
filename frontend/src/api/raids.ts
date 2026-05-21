import type { Raid } from '../types'
import type { InteractiveStateOut } from '../types/battle'
import type { ActionType } from './battles'
import { apiFetch } from './client'

export interface RaidLeaderEntry { account_id: number; name: string; total_damage: number }

export const fetchMyRaid = (): Promise<Raid | null> => apiFetch('/raids/mine')
export const fetchRaid = (raidId: number): Promise<Raid> => apiFetch(`/raids/${raidId}`)
export const fetchRaidLeaderboard = (): Promise<RaidLeaderEntry[]> =>
  apiFetch('/raids/leaderboard?days=7&limit=25')

export const postRaidInteractiveStart = (raidId: number, team: number[]): Promise<InteractiveStateOut> =>
  apiFetch(`/raids/${raidId}/attack/interactive/start`, {
    method: 'POST',
    body: JSON.stringify({ team }),
  })

export const postRaidInteractiveAct = (
  sessionId: string,
  targetUid: string,
  opts?: { actionType?: ActionType; turnNumber?: number },
): Promise<InteractiveStateOut> => {
  const body: Record<string, unknown> = { target_uid: targetUid }
  if (opts?.actionType) body.action_type = opts.actionType
  if (opts?.turnNumber !== undefined) body.turn_number = opts.turnNumber
  return apiFetch<InteractiveStateOut>(`/raids/interactive/${sessionId}/act`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
