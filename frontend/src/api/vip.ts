import { apiFetch, apiPost } from './client'

export interface VipPerks {
  afk_cap_hours: number
  daily_drip_gems: number
  auto_battle_speed: number
  extra_energy_refresh: number
  daily_quest_skip: number
  cosmetic_frame: string
  extra_hero_slots: number
}

export interface VipStatus {
  level: number
  label: string
  xp: number
  xp_to_next: number
  next_label: string | null
  next_perks: Partial<VipPerks> | null
  perks: VipPerks
  drip_available_today: boolean
}

export const fetchVip = (): Promise<VipStatus> => apiFetch<VipStatus>('/vip')
export const claimVipDrip = () =>
  apiPost<{ granted_gems: number; already_claimed: boolean }>('/vip/claim', {})
