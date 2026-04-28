import { useQuery } from '@tanstack/react-query'
import { fetchMyGuild } from '../api/guild'
import { useAuthStore } from '../store/auth'

export function useGuild() {
  const jwt = useAuthStore((s) => s.jwt)
  return useQuery({
    queryKey: ['guild'],
    queryFn: fetchMyGuild,
    refetchOnWindowFocus: true,
    enabled: !!jwt,
  })
}
