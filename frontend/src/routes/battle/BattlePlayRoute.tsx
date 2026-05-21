import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useInteractiveSession } from '../../hooks/useInteractiveSession'
import { BattleHUD } from '../../components/BattleHUD'
import { Battle3DErrorBoundary } from '../../battle3d/Battle3DErrorBoundary'
import type { InteractiveStateOut } from '../../types/battle'
import type { ActionType } from '../../api/battles'
import { postRaidInteractiveAct } from '../../api/raids'
import { toast } from '../../store/ui'

const Battle3DScene = lazy(() =>
  import('../../battle3d/Battle3DScene').then(m => ({ default: m.Battle3DScene }))
)

// Delay between an action resolving and the next auto-pick firing — long
// enough that the player can read the turn-order ribbon + damage numbers
// before the next actor takes over. Tuned slower than the attack clip
// length so the visual feedback fully settles.
const AUTO_PLAY_DELAY_MS = 2200

export default function BattlePlayRoute() {
  const { id: _id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const navState = (location.state as { initState?: InteractiveStateOut; encounterType?: 'stage' | 'raid' } | null) ?? null
  const initState = navState?.initState ?? null
  const encounterType = navState?.encounterType ?? 'stage'

  const { state, act, acting, error } = useInteractiveSession(
    initState,
    encounterType === 'raid' ? { act: postRaidInteractiveAct } : undefined,
  )

  // Auto-play: the stage flow defaults to "Watch in 3D" — we pick the
  // lowest-HP valid target each turn so the player can chill and watch.
  // Toggle off to play manually (skill/limit/specific-target choice).
  const [autoPlay, setAutoPlay] = useState(true)
  const [selectedAction, setSelectedAction] = useState<ActionType>('attack')
  const autoTimerRef = useRef<number | null>(null)
  const toastEventRef = useRef<Record<string, unknown> | null>(null)

  const done = state?.status === 'DONE' || state?.done === true
  const pending = state?.pending
  const teamB = state?.team_b ?? []
  const nameByUid: Record<string, string> = {}
  const templateByUid: Record<string, string> = {}
  for (const p of state?.participants ?? []) {
    if (p.template_code) templateByUid[p.uid] = p.template_code
    nameByUid[p.uid] = p.name
  }
  const actorName = pending
    ? (state?.team_a.find(u => u.uid === pending.actor_uid)?.name ?? pending.actor_name ?? pending.actor_uid)
    : null

  const executeAction = useCallback((targetUid: string, actionType?: ActionType) => {
    const chosenAction = actionType ?? selectedAction
    setAutoPlay(false)
    setSelectedAction('attack')
    act(targetUid, chosenAction)
  }, [act, selectedAction])

  useEffect(() => {
    if (autoTimerRef.current !== null) {
      window.clearTimeout(autoTimerRef.current)
      autoTimerRef.current = null
    }
    if (!autoPlay || !pending || acting || done) return
    const targets = pending.valid_targets ?? pending.enemies?.map(e => e.uid) ?? []
    if (targets.length === 0) return
    // Pick the lowest-HP valid target — matches the legacy auto-mode
    // priority and tends to close out kills faster, which feels better
    // than spreading damage.
    let bestUid = targets[0]
    let bestHp = Infinity
    for (const uid of targets) {
      const unit = teamB.find(u => u.uid === uid)
      const hp = unit?.hp ?? Infinity
      if (hp < bestHp) { bestHp = hp; bestUid = uid }
    }
    autoTimerRef.current = window.setTimeout(() => { act(bestUid) }, AUTO_PLAY_DELAY_MS)
    return () => {
      if (autoTimerRef.current !== null) {
        window.clearTimeout(autoTimerRef.current)
        autoTimerRef.current = null
      }
    }
  }, [autoPlay, pending, acting, done, teamB, act])

  useEffect(() => {
    if (!pending) return
    setSelectedAction('attack')
  }, [pending?.actor_uid, pending?.turn_number])

  useEffect(() => {
    const event = state?.last_event
    if (!event || event === toastEventRef.current) return
    toastEventRef.current = event
    const kind = String(event.type ?? '')
    const eventUid = String(event.actor_uid ?? event.unit ?? '')
    const eventActor = eventUid ? (nameByUid[eventUid] ?? actorName ?? 'Hero') : (actorName ?? 'Hero')
    if (kind === 'SPECIAL') {
      toast.info(`${eventActor} used ${String(event.name ?? pending?.special_name ?? 'a skill')}`)
    } else if (kind === 'LIMIT_BREAK') {
      toast.success(`${eventActor} unleashed ${String(event.name ?? 'Limit Break')}`)
    } else if (kind === 'DEFEND') {
      toast.info(`${eventActor} is defending`)
    } else if (kind === 'TURN_TIMEOUT') {
      toast.error('turn timed out')
    }
  }, [actorName, nameByUid, pending?.special_name, state?.last_event])

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

  const rewards = state.rewards ?? null

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
            validTargets={pending?.valid_targets ?? pending?.enemies?.map(e => e.uid) ?? []}
            onAct={pending ? (targetUid) => executeAction(targetUid, selectedAction) : undefined}
          />
        </Suspense>
      </Battle3DErrorBoundary>

      <BattleHUD
        teamA={state.team_a}
        teamB={state.team_b}
        onAct={pending ? executeAction : undefined}
        onSelectAction={(actionType) => {
          setAutoPlay(false)
          setSelectedAction(actionType)
        }}
        pendingActorUid={pending?.actor_uid ?? null}
        pending={pending ?? null}
        selectedAction={selectedAction}
        validTargets={pending?.valid_targets ?? pending?.enemies?.map(e => e.uid) ?? []}
        acting={acting}
        done={done}
        rewards={rewards}
        onClose={() => {
          if (encounterType === 'raid') {
            navigate('/app/raids')
            return
          }
          const r = state.rewards as (Record<string, unknown> | null | undefined)
          const unlocks = Array.isArray(r?.milestone_unlocks) ? (r!.milestone_unlocks as number[]) : []
          navigate('/app/stages', unlocks.length > 0 ? { state: { milestoneUnlocks: unlocks } } : undefined)
        }}
        templateByUid={templateByUid}
        turnStartedAt={state.turn_started_at ?? null}
        turnTimeoutS={state.turn_timeout_s}
        turnOrderPeek={state.turn_order_peek ?? []}
      />

      {/* Auto-play toggle — top right. Pause to take manual control. */}
      {!done && (
        <button
          onClick={() => setAutoPlay(v => !v)}
          style={{
            position: 'absolute', top: 16, right: 16,
            background: autoPlay ? 'rgba(0, 255, 224, 0.18)' : 'rgba(0,0,0,0.55)',
            color: autoPlay ? 'var(--accent, #00ffe0)' : '#fff',
            border: `1px solid ${autoPlay ? 'rgba(0, 255, 224, 0.6)' : 'rgba(255,255,255,0.2)'}`,
            padding: '6px 12px', borderRadius: 6, fontSize: 12, fontWeight: 700,
            letterSpacing: 0.4, cursor: 'pointer', backdropFilter: 'blur(6px)',
          }}
        >
          {autoPlay ? '⚡ AUTO' : '⏸ MANUAL'}
        </button>
      )}

      {error && (
        <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', background: 'var(--color-error)', color: '#fff', padding: '8px 16px', borderRadius: 6, fontSize: 13 }}>
          {error}
        </div>
      )}

      {pending && !done && !autoPlay && (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.7)', color: '#fff', padding: '8px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600 }}>
          {actorName} — {selectedAction === 'skill' ? `pick a target for ${pending.special_name ?? 'skill'}` : `pick a target for ${selectedAction}`}
        </div>
      )}
    </div>
  )
}
