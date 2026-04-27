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

export function postAct(sessionId: string, targetUid: string): Promise<InteractiveStateOut> {
  return apiFetch<InteractiveStateOut>(`/battles/interactive/${sessionId}/act`, {
    method: 'POST',
    body: JSON.stringify({ target_uid: targetUid }),
  })
}

export function fetchBattle(battleId: string | number): Promise<BattleOut> {
  return apiFetch<BattleOut>(`/battles/${battleId}`)
}
