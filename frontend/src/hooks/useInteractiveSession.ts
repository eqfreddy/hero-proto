import { useState, useCallback, useEffect, useRef } from 'react'
import { postAct, fetchInteractiveState } from '../api/battles'
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

  // Turn-timer poll: when the client-side countdown reaches 0, hit
  // GET /interactive/{id}. The server lazy-expires stuck sessions to
  // LOSS, so this both proves the timer isn't a UI lie AND unwedges
  // crashed/AFK sessions for the player. We add a 2s grace beyond the
  // server timeout to absorb clock skew.
  const pollTimerRef = useRef<number | null>(null)
  useEffect(() => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
    if (!state) return
    if (state.status === 'DONE') return
    if (state.turn_started_at == null) return
    const timeoutS = state.turn_timeout_s ?? 120
    const nowS = Date.now() / 1000
    const elapsed = nowS - state.turn_started_at
    const remainingMs = Math.max(0, (timeoutS - elapsed + 2) * 1000)
    pollTimerRef.current = window.setTimeout(async () => {
      try {
        const next = await fetchInteractiveState(state.session_id)
        setState(next)
      } catch {
        // ignore — next user action will surface the error
      }
    }, remainingMs)
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [state?.session_id, state?.turn_started_at, state?.status, state?.turn_timeout_s])

  return { state, setState, act, acting, error }
}
