import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { isNative } from '../../native'

export default function BattleReplayRoute() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  useEffect(() => {
    if (!id) return
    // Legacy 2D viewer is a backend-served HTML page — unreachable from
    // Capacitor's file:// origin. On native, redirect to the battle hub
    // instead of trying to load a 404.
    if (isNative()) {
      navigate('/app/battle', { replace: true })
      return
    }
    window.location.replace(`/app/static/battle-arena.html?battle_id=${id}`)
  }, [id, navigate])

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--muted)' }}>
      Loading battle…
    </div>
  )
}
