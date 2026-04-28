import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useInteractiveSession } from '../../hooks/useInteractiveSession'
import { BattleHUD } from '../../components/BattleHUD'
import type { InteractiveStateOut } from '../../types/battle'

export default function BattlePlayRoute() {
  const { id: _id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const initState = (location.state as { initState?: InteractiveStateOut } | null)?.initState ?? null

  const { state, act, acting, error } = useInteractiveSession(initState)

  if (!state) {
    return (
      <div style={{ color: 'var(--color-muted)', padding: 24 }}>
        No session found.{' '}
        <button onClick={() => navigate('/battle/setup')} style={{ color: 'var(--color-accent)', background: 'none', border: 'none', cursor: 'pointer' }}>
          Start a new battle
        </button>
      </div>
    )
  }

  const done = state.done ?? false
  const pending = state.pending
  const rewards = state.rewards ?? null

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh', background: 'var(--color-bg)' }}>
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'rgba(255,255,255,0.08)', fontSize: 48, fontWeight: 900, letterSpacing: 4 }}>BATTLE</div>
      </div>

      <BattleHUD
        teamA={state.team_a}
        teamB={state.team_b}
        onAct={pending ? act : undefined}
        pendingActorUid={pending?.actor_uid ?? null}
        validTargets={pending?.valid_targets ?? []}
        acting={acting}
        done={done}
        rewards={rewards}
        onClose={() => navigate('/app/stages')}
      />

      {error && (
        <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', background: 'var(--color-error)', color: '#fff', padding: '8px 16px', borderRadius: 6, fontSize: 13 }}>
          {error}
        </div>
      )}

      {pending && !done && (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.7)', color: '#fff', padding: '8px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600 }}>
          {state.team_a.find(u => u.uid === pending.actor_uid)?.name ?? pending.actor_uid} — pick a target
        </div>
      )}
    </div>
  )
}
