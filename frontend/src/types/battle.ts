export interface CombatUnit {
  uid: string
  name: string
  hp: number
  max_hp: number
  atk: number
  def: number
  spd: number
  dead: boolean
  portrait_url?: string
}

export interface BattleLog {
  event: string
  [key: string]: unknown
}

export interface BattleOut {
  id: number
  account_id: number
  stage_id?: number
  log: BattleLog[]
  created_at?: string
}

export interface InteractivePending {
  actor_uid: string
  valid_targets: string[]
}

export interface InteractiveStateOut {
  session_id: string
  team_a: CombatUnit[]
  team_b: CombatUnit[]
  pending: InteractivePending | null
  rewards?: Record<string, number>
  done?: boolean
}

export interface PostBattlePayload {
  stage_id: number
  team: number[]
  target_priority?: string
}

export interface PostInteractiveStartPayload {
  stage_id: number
  team: number[]
}
