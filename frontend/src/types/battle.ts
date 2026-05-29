export interface CombatUnit {
  uid: string
  name: string
  hp: number
  max_hp: number
  atk: number
  def: number
  spd: number
  dead: boolean
  side?: 'A' | 'B'
  portrait_url?: string
  /** Phase A: surfaced by backend UnitSnapshot. */
  shielded?: boolean
  defending?: boolean
  statuses?: string[]
  mana?: number
  mana_cost?: number
  limit_gauge?: number
  limit_gauge_max?: number
  /** System Integrity (weakness-break). integrity_max === 0 means no bar (heroes). */
  integrity?: number
  integrity_max?: number
  burnout?: number
  crashed?: boolean
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
  actor_name?: string
  turn_number?: number
  enemies?: { uid: string; name: string; hp: number; max_hp: number }[]
  valid_targets?: string[]
  /** Enemy uids the acting unit may Delete this turn (Crashed + threshold). */
  valid_delete_targets?: string[]
  /** Phase A + System Integrity: per-action availability for the HUD action bar. */
  actions?: Record<'attack' | 'skill' | 'limit' | 'defend' | 'delete', { enabled: boolean; reason: string | null }>
  special_name?: string | null
  special_kind?: string | null
  special_cooldown_left?: number
  mana?: number
  mana_cost?: number
  limit_gauge?: number
  limit_gauge_max?: number
}

export interface InteractiveParticipant {
  uid: string
  side: 'A' | 'B'
  name: string
  role?: string
  level?: number
  max_hp?: number
  template_code?: string
  rarity?: string
  faction?: string
  rig?: string
}

export interface InteractiveStateOut {
  session_id: string
  status?: string
  team_a: CombatUnit[]
  team_b: CombatUnit[]
  pending: InteractivePending | null
  rewards?: Record<string, number>
  done?: boolean
  battle_id?: number
  stage_code?: string | null
  last_event?: Record<string, unknown> | null
  participants?: InteractiveParticipant[]
  /** Unix epoch seconds when the current WAITING turn started.
   * Null when not waiting. Client renders countdown =
   * turn_timeout_s - (now - turn_started_at). */
  turn_started_at?: number | null
  /** Server-side turn timeout in seconds. Constant for the session. */
  turn_timeout_s?: number
  /** Phase E — next-N actor uids in turn order. Empty when DONE. */
  turn_order_peek?: string[]
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
