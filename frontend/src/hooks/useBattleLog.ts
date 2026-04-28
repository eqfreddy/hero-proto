import { useQuery } from '@tanstack/react-query'
import { fetchBattle } from '../api/battles'
import type { BattleOut } from '../types/battle'

export function useBattleLog(battleId: string | number | undefined) {
  return useQuery<BattleOut>({
    queryKey: ['battle', battleId],
    queryFn: () => fetchBattle(battleId!),
    enabled: battleId != null,
    staleTime: Infinity,
  })
}
