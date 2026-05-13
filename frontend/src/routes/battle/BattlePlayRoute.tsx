import { lazy, Suspense } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useInteractiveSession } from '../../hooks/useInteractiveSession'
import { BattleHUD } from '../../components/BattleHUD'
import { Battle3DErrorBoundary } from '../../battle3d/Battle3DErrorBoundary'
import type { InteractiveStateOut } from '../../types/battle'

const Battle3DScene = lazy(() =>
  import('../../battle3d/Battle3DScene').then(m => ({ default: m.Battle3DScene }))
)

export default function BattlePlayRoute() {
  const { id: _id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const initState = (location.state as { initState?: InteractiveStateOut } | null)?.initState ?? null

  const { state, act, acting, error } = useInteractiveSession(initState)

  const done = state?.status === 'DONE' || state?.done === true

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

  const pending = state.pending
  const rewards = state.rewards ?? null
  const templateByUid: Record<string, string> = {}
  for (const p of state.participants ?? []) {
    if (p.template_code) templateByUid[p.uid] = p.template_code
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh', background: 'var(--color-bg)' }}>
      <Battle3DErrorBoundary>
        <Suspense fallback={
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ color: 'rgba(255,255,255,0.08)', fontSize: 48, fontWeight: 900, letterSpacing: 4 }}>BATTLE</div>
          </div>
        }>
          <Battle3DScene
            teamA={state.team_a}
            teamB={state.team_b}
            stageCode={state.stage_code ?? null}
            pendingActorUid={pending?.actor_uid ?? null}
            lastEvent={state.last_event ?? null}
            done={done}
            templateByUid={templateByUid}
            validTargets={pending?.valid_targets ?? []}
            onAct={pending ? act : undefined}
          />
        </Suspense>
      </Battle3DErrorBoundary>

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
        templateByUid={templateByUid}
        turnStartedAt={state.turn_started_at ?? null}
        turnTimeoutS={state.turn_timeout_s}
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
