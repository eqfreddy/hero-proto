import { apiFetch, apiPost } from './client'

export interface Material {
  code: string
  name: string
  rarity: string
  description: string
  icon: string
  quantity: number
}

export interface GearOutput {
  slot?: string
  rarity?: string
  set_code?: string
}

export interface Recipe {
  code: string
  name: string
  description: string
  materials: Record<string, number>
  coin_cost: number
  gem_cost: number
  output: Record<string, number>
  gear_output: GearOutput | null
  icon: string
  craftable: boolean
  blocking_reason: string | null
}

export const fetchCrafting = (): Promise<{ materials: Material[]; recipes: Recipe[] }> =>
  Promise.all([apiFetch<Material[]>('/crafting/materials'), apiFetch<Recipe[]>('/crafting/recipes')])
    .then(([materials, recipes]) => ({ materials, recipes }))

export const craftRecipe = (code: string) => apiPost(`/crafting/${code}/craft`, {})
