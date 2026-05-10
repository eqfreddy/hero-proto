import { useQuery } from '@tanstack/react-query'
import { fetchHeroes } from '../api/heroes'

export function useHeroes() {
  return useQuery({ queryKey: ['heroes'], queryFn: fetchHeroes, staleTime: 5 * 60_000 })
}

// Derive a single hero from the cached roster list. `/heroes/{id}/preview`
// returns an upgrade-preview shape, not a full Hero — so we can't fetch
// per-id without a new endpoint. Reuses the list cache.
export function useHero(id: number) {
  const list = useHeroes()
  return {
    ...list,
    data: list.data?.find((h) => h.id === id),
  }
}
