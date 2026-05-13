import { useQuery } from '@tanstack/react-query'
import { fetchMilestones } from '../api/milestones'
import type { MilestonesResponse } from '../api/milestones'

/**
 * Fetches milestone list + per-account claim state from GET /stages/milestones.
 * Gracefully returns null data when the backend endpoint is not yet live (404)
 * so the board renders without crashing.
 */
export function useMilestones() {
  return useQuery<MilestonesResponse | null>({
    queryKey: ['milestones'],
    queryFn: async () => {
      try {
        return await fetchMilestones()
      } catch (err: unknown) {
        // 404 means backend not yet live — render with empty milestones
        if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 404) {
          return null
        }
        throw err
      }
    },
    staleTime: 60_000,
    retry: (failureCount, err: unknown) => {
      if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 404) return false
      return failureCount < 2
    },
  })
}
