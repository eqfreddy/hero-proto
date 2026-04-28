import { useState, useCallback } from 'react'
import { postAct } from '../api/battles'
import type { InteractiveStateOut } from '../types/battle'

export function useInteractiveSession(initialState: InteractiveStateOut | null) {
  const [state, setState] = useState<InteractiveStateOut | null>(initialState)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const act = useCallback(async (targetUid: string) => {
    if (!state) return
    setActing(true)
    setError(null)
    try {
      const next = await postAct(state.session_id, targetUid)
      setState(next)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setActing(false)
    }
  }, [state])

  return { state, setState, act, acting, error }
}
