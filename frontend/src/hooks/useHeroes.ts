import { useQuery } from '@tanstack/react-query'
import { fetchHeroes, fetchHero } from '../api/heroes'

export function useHeroes() {
  return useQuery({ queryKey: ['heroes'], queryFn: fetchHeroes, staleTime: 5 * 60_000 })
}

export function useHero(id: number) {
  return useQuery({ queryKey: ['heroes', id], queryFn: () => fetchHero(id), staleTime: 5 * 60_000 })
}
