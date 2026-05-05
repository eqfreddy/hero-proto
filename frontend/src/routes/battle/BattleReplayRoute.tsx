import { useEffect } from 'react'
import { useParams } from 'react-router-dom'

export default function BattleReplayRoute() {
  const { id } = useParams<{ id: string }>()

  useEffect(() => {
    if (id) window.location.replace(`/app/static/battle-arena.html?battle_id=${id}`)
  }, [id])

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--muted)' }}>
      Loading battle…
    </div>
  )
}
