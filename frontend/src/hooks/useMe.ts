import { useQuery } from '@tanstack/react-query'
import { fetchMe } from '../api/me'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  })
}
