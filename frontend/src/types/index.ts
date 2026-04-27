export interface Me {
  id: number
  email: string
  coins: number
  gems: number
  shards: number
  access_cards: number
  free_summon_credits: number
  energy: number
  energy_cap: number
  pulls_since_epic: number
  stages_cleared: string[]
  arena_rating: number
  arena_wins: number
  arena_losses: number
  account_level: number
  account_xp: number
  qol_unlocks: Record<string, unknown>
  active_cosmetic_frame: string
}

export interface HeroTemplate {
  id: number
  code: string
  name: string
  rarity: 'COMMON' | 'UNCOMMON' | 'RARE' | 'EPIC' | 'LEGENDARY' | 'MYTH'
  role: 'ATK' | 'DEF' | 'SUP'
  faction: 'RESISTANCE' | 'CORP_GREED' | 'EXILE' | 'NEUTRAL'
  attack_kind: 'melee' | 'ranged'
  base_hp: number
  base_atk: number
  base_def: number
  base_spd: number
}

export interface Hero {
  id: number
  template: HeroTemplate
  level: number
  stars: number
  special_level: number
  power: number
  hp: number
  atk: number
  def_: number
  spd: number
  has_variance: boolean
  variance_net: number
  dupe_count: number
  instance_ids: number[]
  has_bust?: boolean
  has_card?: boolean
}

export interface Stage {
  id: number
  code: string
  name: string
  order: number
  energy_cost: number
  recommended_power: number
  coin_reward: number
  first_clear_gems: number
  first_clear_shards: number
  cleared: boolean
  difficulty_tier: 'NORMAL' | 'HARD' | 'NIGHTMARE'
  requires_code: string | null
  locked: boolean
}

export interface Guild {
  id: number
  name: string
  tag: string
  description: string
  member_count: number
  members?: GuildMember[]
}

export interface GuildMember {
  account_id: number
  name: string
  role: 'LEADER' | 'OFFICER' | 'MEMBER'
  arena_rating: number
}

export interface Notification {
  id: number
  title: string
  body: string | null
  icon: string | null
  link: string | null
  read_at: string | null
  created_at: string
}

export interface ShopProduct {
  sku: string
  title: string
  description: string
  kind: string
  price_cents: number
  currency_code: string
  contents: Record<string, unknown>
  has_stripe: boolean
}

export interface BattleLog {
  id: number
  stage_code: string
  outcome: 'WIN' | 'LOSS'
  created_at: string
  log: BattleEvent[]
}

export interface BattleEvent {
  type: string
  actor?: string
  target?: string
  amount?: number
  crit?: boolean
  channel?: 'melee' | 'ranged'
  source?: string
  [key: string]: unknown
}

export interface UnitSnapshot {
  uid: string
  name: string
  side: 'A' | 'B'
  role: string
  hp: number
  max_hp: number
  dead: boolean
  shielded: boolean
  limit_gauge: number
  limit_gauge_max: number
}

export interface InteractiveState {
  session_id: string
  status: 'WAITING' | 'DONE'
  pending: {
    actor_uid: string
    actor_name: string
    turn_number: number
    enemies: UnitSnapshot[]
  } | null
  log_delta: BattleEvent[]
  team_a: UnitSnapshot[]
  team_b: UnitSnapshot[]
  outcome: string | null
  rewards: Record<string, unknown> | null
  participants: unknown[]
}

export interface Raid {
  id: number
  boss_name: string
  remaining_hp: number
  max_hp: number
  status: string
  guild_id: number
}
