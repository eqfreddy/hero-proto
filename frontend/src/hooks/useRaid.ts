import { useQuery } from '@tanstack/react-query'
import { fetchMyRaid } from '../api/raids'
import { useAuthStore } from '../store/auth'

export function useRaid() {
  const jwt = useAuthStore((s) => s.jwt)
  return useQuery({
    queryKey: ['raid'],
    queryFn: fetchMyRaid,
    refetchInterval: 30_000,
    enabled: !!jwt,
  })
}
