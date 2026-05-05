import { apiFetch, apiPost } from './client'

export type GearSlot =
  | 'WEAPON' | 'HEAD' | 'CHEST' | 'HANDS' | 'WRIST' | 'LEGS' | 'FEET' | 'RING' | 'AMULET'

export type GearRarity = 'COMMON' | 'RARE' | 'EPIC' | 'LEGENDARY'

export type GearSetCode =
  | 'VITAL' | 'OFFENSE' | 'DEFENSE' | 'SWIFT' | 'VIOLENT' | 'LIFESTEAL'

export interface GearOut {
  id: number
  slot: GearSlot
  rarity: GearRarity
  set: GearSetCode
  stats: Partial<Record<'hp' | 'atk' | 'def' | 'spd', number>>
  equipped_on: number | null
  locked: boolean
  name: string | null
  flavor: string | null
}

export const ARMOR_SLOTS: GearSlot[] = ['HEAD', 'CHEST', 'HANDS', 'WRIST', 'LEGS', 'FEET']
export const ALL_SLOTS: GearSlot[] = ['WEAPON', ...ARMOR_SLOTS, 'RING', 'AMULET']

export const SLOT_META: Record<GearSlot, { label: string; icon: string }> = {
  WEAPON: { label: 'Weapon', icon: '⚔️' },
  HEAD:   { label: 'Head',   icon: '🪖' },
  CHEST:  { label: 'Chest',  icon: '🦺' },
  HANDS:  { label: 'Hands',  icon: '🥊' },
  WRIST:  { label: 'Wrist',  icon: '⌚' },
  LEGS:   { label: 'Legs',   icon: '👖' },
  FEET:   { label: 'Feet',   icon: '👞' },
  RING:   { label: 'Ring',   icon: '💍' },
  AMULET: { label: 'Amulet', icon: '📿' },
}

export const SET_META: Record<GearSetCode, { label: string; bonus: string; pieces: 2 | 4 }> = {
  VITAL:     { label: 'Vital',     bonus: '+15% HP',                              pieces: 2 },
  OFFENSE:   { label: 'Offense',   bonus: '+15% ATK',                             pieces: 2 },
  DEFENSE:   { label: 'Defense',   bonus: '+15% DEF',                             pieces: 2 },
  SWIFT:     { label: 'Swift',     bonus: '+15% SPD',                             pieces: 2 },
  VIOLENT:   { label: 'Violent',   bonus: '20% extra turn after acting',          pieces: 4 },
  LIFESTEAL: { label: 'Lifesteal', bonus: '30% damage healed',                    pieces: 4 },
}

export const RARITY_COLOR: Record<GearRarity, string> = {
  COMMON:    'var(--r-common)',
  RARE:      'var(--r-rare)',
  EPIC:      'var(--r-epic)',
  LEGENDARY: 'var(--r-legendary)',
}

// ── The Veteran IT Set — story-reward armor pieces ─────────────────────────
// Mirror of app/named_gear.py NAMED_GEAR — keep in sync if names change.
export interface VeteranSetPiece {
  name: string
  icon: string
  slot: GearSlot
  source: string  // human-readable acquisition hint
}
export const VETERAN_IT_SET: VeteranSetPiece[] = [
  { name: 'Help Desk Headset',         icon: '🎧', slot: 'HEAD',  source: 'Chapter 1' },
  { name: 'Power-Suit Jacket',         icon: '🧥', slot: 'CHEST', source: 'Chapter 2' },
  { name: 'Signing Gauntlets',         icon: '🥊', slot: 'HANDS', source: 'Chapter 4 — Corp Greed' },
  { name: 'Burner Phone Wristband',    icon: '📡', slot: 'WRIST', source: 'Chapter 4 — Resistance' },
  { name: 'Cargo Pants of Many Tabs',  icon: '👖', slot: 'LEGS',  source: 'Level 50 — alignment fork' },
  { name: 'All-Terrain Loafers',       icon: '👞', slot: 'FEET',  source: 'Chapter 3' },
]

// Chapter code → named piece preview (mirror of CHAPTER_END_NAMED_GEAR in
// app/account_level.py). Used by the Story tab to tease the reward.
export const CHAPTER_NAMED_GEAR: Record<string, VeteranSetPiece> = {
  onboarding_arc:        VETERAN_IT_SET[0],  // Help Desk Headset
  middle_management_arc: VETERAN_IT_SET[1],  // Power-Suit Jacket
  exec_floor_arc:        VETERAN_IT_SET[5],  // All-Terrain Loafers
  resistance_arc:        VETERAN_IT_SET[3],  // Burner Phone Wristband
  corpgreed_arc:         VETERAN_IT_SET[2],  // Signing Gauntlets
}

export interface SalvageResult {
  salvaged_gear_id: number
  rarity: string
  yielded: Record<string, number>
}

export const fetchGear = (): Promise<GearOut[]> => apiFetch('/gear/mine?limit=1000')

export const equipGear = (gearId: number, heroInstanceId: number) =>
  apiPost<GearOut>(`/gear/${gearId}/equip`, { hero_instance_id: heroInstanceId })

export const unequipGear = (gearId: number) =>
  apiPost<GearOut>(`/gear/${gearId}/unequip`, {})

export const toggleLockGear = (gearId: number): Promise<{ id: number; locked: boolean }> =>
  apiPost(`/gear/${gearId}/lock`, {})

export const salvageGear = (gearId: number): Promise<SalvageResult> =>
  apiPost(`/gear/${gearId}/salvage`, {})
