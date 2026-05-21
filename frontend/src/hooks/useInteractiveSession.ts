import { useState, useCallback, useEffect, useRef } from 'react'
import { postAct, fetchInteractiveState, type ActionType } from '../api/battles'
import type { InteractiveStateOut } from '../types/battle'

interface Transport {
  act?: (
    sessionId: string,
    targetUid: string,
    opts?: { actionType?: ActionType; turnNumber?: number },
  ) => Promise<InteractiveStateOut>
  fetch?: (sessionId: string) => Promise<InteractiveStateOut>
}

export function useInteractiveSession(initialState: InteractiveStateOut | null, transport?: Transport) {
  const [state, setState] = useState<InteractiveStateOut | null>(initialState)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const actRequest = transport?.act ?? postAct
  const fetchRequest = transport ? transport.fetch : fetchInteractiveState

  const act = useCallback(async (targetUid: string, actionType?: ActionType) => {
    if (!state) return
    setActing(true)
    setError(null)
    try {
      const next = await actRequest(state.session_id, targetUid, { actionType })
      setState(next)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setActing(false)
    }
  }, [actRequest, state])

  const pollTimerRef = useRef<number | null>(null)
  useEffect(() => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
    if (!state || !fetchRequest) return
    if (state.status === 'DONE') return
    if (state.turn_started_at == null) return
    const timeoutS = state.turn_timeout_s ?? 120
    const nowS = Date.now() / 1000
    const elapsed = nowS - state.turn_started_at
    const remainingMs = Math.max(0, (timeoutS - elapsed + 2) * 1000)
    pollTimerRef.current = window.setTimeout(async () => {
      try {
        const next = await fetchRequest(state.session_id)
        setState(next)
      } catch {
        // ignore; next user action will surface the error
      }
    }, remainingMs)
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [fetchRequest, state?.session_id, state?.turn_started_at, state?.status, state?.turn_timeout_s])

  return { state, setState, act, acting, error }
}
