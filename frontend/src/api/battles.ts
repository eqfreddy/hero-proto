import { apiFetch } from './client'
import type { BattleOut, InteractiveStateOut, PostBattlePayload, PostInteractiveStartPayload } from '../types/battle'

export function postBattle(payload: PostBattlePayload): Promise<BattleOut> {
  return apiFetch<BattleOut>('/battles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function postInteractiveStart(payload: PostInteractiveStartPayload): Promise<InteractiveStateOut> {
  return apiFetch<InteractiveStateOut>('/battles/interactive/start', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export type ActionType = 'attack' | 'skill' | 'limit' | 'defend' | 'delete'

export function postAct(
  sessionId: string,
  targetUid: string,
  opts?: { actionType?: ActionType; turnNumber?: number },
): Promise<InteractiveStateOut> {
  const body: Record<string, unknown> = { target_uid: targetUid }
  if (opts?.actionType) body.action_type = opts.actionType
  if (opts?.turnNumber !== undefined) body.turn_number = opts.turnNumber
  return apiFetch<InteractiveStateOut>(`/battles/interactive/${sessionId}/act`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchInteractiveState(sessionId: string): Promise<InteractiveStateOut> {
  return apiFetch<InteractiveStateOut>(`/battles/interactive/${sessionId}`)
}

export function fetchBattle(battleId: string | number): Promise<BattleOut> {
  return apiFetch<BattleOut>(`/battles/${battleId}`)
}
