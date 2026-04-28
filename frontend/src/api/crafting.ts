import { apiFetch, apiPost } from './client'
export interface Material { code: string; name: string; rarity: string; description: string; icon: string; quantity: number }
export interface Recipe { id: number; code: string; name: string; description: string; materials: Record<string,number>; coin_cost: number; gem_cost: number; craftable: boolean; blocking_reason: string | null }
export const fetchCrafting = (): Promise<{ materials: Material[]; recipes: Recipe[] }> =>
  Promise.all([apiFetch<Material[]>('/crafting/materials'), apiFetch<Recipe[]>('/crafting/recipes')])
    .then(([materials, recipes]) => ({ materials, recipes }))
export const craftRecipe = (code: string) => apiPost(`/crafting/${code}/craft`, {})
