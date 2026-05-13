import { apiFetch, apiPost } from './client'

// ── Types ──────────────────────────────────────────────────────────────────

export interface MilestoneItem {
  id: number
  stage_count: number
  template_shards: number
  legend_shard_chance: number
  label: string
  unlocked: boolean
  claimed: boolean
  claimed_at: string | null
  legend_shards_granted: number | null
}

export interface NextMilestone {
  id: number
  stage_count: number
  stages_to_go: number
  template_shards: number
  legend_shard_chance: number
  label: string
}

export interface MilestonesResponse {
  stages_cleared_count: number
  next_milestone: NextMilestone | null
  milestones: MilestoneItem[]
  legend_boss_shards: number
  legend_summon_cost: number
  pity_counter: number
  pity_floor: number
}

export interface ClaimMilestoneResponse {
  milestone_id: number
  template_shards_granted: number
  legend_shards_granted: number
  legend_boss_shards_balance: number
  pity_counter: number
}

// ── API calls ──────────────────────────────────────────────────────────────

export const fetchMilestones = (): Promise<MilestonesResponse> =>
  apiFetch<MilestonesResponse>('/stages/milestones')

export const claimMilestone = (id: number): Promise<ClaimMilestoneResponse> =>
  apiPost<ClaimMilestoneResponse>(`/stages/milestones/${id}/claim`, {})

/** POST /summon/legend-boss — deducts 30 legend_boss_shards, returns a hero */
export const summonLegendBoss = (): Promise<unknown> =>
  apiPost('/summon/legend-boss', {})
