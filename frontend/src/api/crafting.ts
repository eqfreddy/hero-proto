import { apiFetch, apiPost } from './client'
export interface Material { code: string; name: string; rarity: string; description: string; icon: string; quantity: number }
export interface Recipe { id: number; name: string; description: string; materials: Record<string,number>; coin_cost: number; gem_cost: number; craftable: boolean; blocking_reason: string | null }
export const fetchCrafting = (): Promise<{ materials: Material[]; recipes: Recipe[] }> => apiFetch('/crafting')
export const craftRecipe = (id: number) => apiPost(`/crafting/${id}/craft`, {})
