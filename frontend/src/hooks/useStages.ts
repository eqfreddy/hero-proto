import { useQuery } from '@tanstack/react-query'
import { fetchStages } from '../api/stages'
import { useHeroes } from './useHeroes'
import { useMemo } from 'react'

export function useStages() {
  return useQuery({ queryKey: ['stages'], queryFn: fetchStages, staleTime: 10 * 60_000 })
}

export function useTeamPower(): number {
  const { data: heroes } = useHeroes()
  return useMemo(() => {
    if (!heroes?.length) return 0
    const top3 = [...heroes].sort((a, b) => b.power - a.power).slice(0, 3)
    return top3.reduce((s, h) => s + h.power, 0)
  }, [heroes])
}
