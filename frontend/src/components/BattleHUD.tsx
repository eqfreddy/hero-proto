import { useEffect, useState } from 'react'
import type { CombatUnit, InteractivePending } from '../types/battle'
import type { ActionType } from '../api/battles'

const BUST_BASE = '/app/static/heroes/busts/'

interface BattleHUDProps {
  teamA: CombatUnit[]
  teamB: CombatUnit[]
  onAct: ((targetUid: string, actionType?: ActionType) => void) | undefined
  pendingActorUid: string | null
  pending?: InteractivePending | null
  validTargets: string[]
  acting: boolean
  done: boolean
  rewards: Record<string, number> | null
  onClose: () => void
  templateByUid?: Record<string, string>
  /** Unix epoch seconds when the current waiting turn started (server-side). */
  turnStartedAt?: number | null
  /** Server-side per-turn timeout (constant per session). */
  turnTimeoutS?: number
  /** Phase E — next-N actor uids surfaced by the resolver. */
  turnOrderPeek?: string[]
}

function TurnOrderRibbon({ peek, units, templateByUid, currentUid }: {
  peek: string[]
  units: CombatUnit[]
  templateByUid?: Record<string, string>
  currentUid?: string | null
}) {
  if (!peek || peek.length === 0) return null
  const byUid = new Map(units.map(u => [u.uid, u]))
  return (
    <div style={{
      position: 'absolute', top: 56, left: '50%', transform: 'translateX(-50%)',
      display: 'flex', gap: 4, pointerEvents: 'none',
      background: 'rgba(0,0,0,0.45)', borderRadius: 6, padding: '4px 6px',
      border: '1px solid rgba(255,255,255,0.08)',
    }}>
      {peek.map((uid, i) => {
        const u = byUid.get(uid)
        if (!u) return null
        const tc = templateByUid?.[uid]
        const bust = tc ? `${BUST_BASE}${tc}.png` : null
        const isCurrent = uid === currentUid && i === 0
        const sideRing = (u.side ?? (uid.startsWith('a') ? 'A' : 'B')) === 'A' ? '#00e0d0' : '#ff5a78'
        return (
          <div key={`${uid}-${i}`} style={{
            position: 'relative',
            width: i === 0 ? 36 : 28, height: i === 0 ? 36 : 28,
            borderRadius: 4, overflow: 'hidden',
            border: `1.5px solid ${isCurrent ? '#ffd86b' : sideRing}`,
            background: 'rgba(0,0,0,0.55)',
            opacity: u.dead ? 0.3 : 1 - i * 0.08,
            boxShadow: isCurrent ? '0 0 12px rgba(255,216,107,0.55)' : 'none',
          }} title={`${u.name}${isCurrent ? ' · NOW' : i === 1 ? ' · next' : ''}`}>
            {bust ? (
              <img src={bust} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
            ) : (
              <div style={{
                fontSize: i === 0 ? 13 : 10, fontWeight: 700,
                color: sideRing, display: 'flex', alignItems: 'center',
                justifyContent: 'center', height: '100%',
              }}>{u.name.slice(0, 1)}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Live per-turn countdown banner. Drives a once-per-second tick so the
 * UI shows the player how long they have before the server forfeits the
 * battle. Hidden when no turn is in progress. */
function TurnTimer({ startedAt, timeoutS }: { startedAt: number; timeoutS: number }) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => window.clearInterval(id)
  }, [])
  const remaining = Math.max(0, Math.ceil(timeoutS - (now - startedAt)))
  const lowFraction = remaining <= timeoutS * 0.25
  const critical = remaining <= 10
  const color = critical ? '#e85a78' : lowFraction ? '#e8a35a' : '#cfd6dd'
  return (
    <div style={{
      position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
      background: 'rgba(0,0,0,0.65)', border: `1px solid ${color}`,
      borderRadius: 16, padding: '4px 14px',
      fontSize: 13, fontWeight: 800, color,
      display: 'flex', alignItems: 'center', gap: 6,
      pointerEvents: 'none', letterSpacing: 0.5, fontVariantNumeric: 'tabular-nums',
    }}>
      <span>⏱</span>
      <span>{remaining}s</span>
      {critical && <span style={{ fontSize: 10, opacity: 0.85, marginLeft: 4 }}>FORFEIT IMMINENT</span>}
    </div>
  )
}

const STATUS_GLYPH: Record<string, { icon: string; color: string; label: string }> = {
  POISON:      { icon: '☠', color: '#9ee37d', label: 'Poison' },
  BURN:        { icon: '🔥', color: '#ff8c5a', label: 'Burn' },
  STUN:        { icon: '⚡', color: '#ffd86b', label: 'Stun' },
  FREEZE:      { icon: '❄', color: '#7fd8ff', label: 'Freeze' },
  SHIELD:      { icon: '◆', color: '#a8c4ff', label: 'Shield' },
  REFLECT:     { icon: '↺', color: '#d8a8ff', label: 'Reflect' },
  HEAL_BLOCK:  { icon: '✕', color: '#ff7da3', label: 'Heal Block' },
  ATK_UP:      { icon: '▲', color: '#ff8c8c', label: 'ATK Up' },
  DEF_DOWN:    { icon: '▽', color: '#8c8cff', label: 'DEF Down' },
  DEFENDING:   { icon: '🛡', color: '#a8c4ff', label: 'Defending' },
}

function StatusStrip({ statuses }: { statuses?: string[] }) {
  if (!statuses?.length) return null
  return (
    <div style={{ display: 'flex', gap: 3, marginTop: 3, flexWrap: 'wrap' }}>
      {statuses.slice(0, 5).map((s) => {
        const g = STATUS_GLYPH[s] ?? { icon: '·', color: '#aaa', label: s }
        return (
          <span key={s} title={g.label}
            style={{
              fontSize: 10, lineHeight: 1, padding: '1px 3px',
              borderRadius: 2, background: 'rgba(0,0,0,0.55)',
              color: g.color, fontWeight: 700,
            }}>{g.icon}</span>
        )
      })}
    </div>
  )
}

function UnitCard({
  unit,
  isTarget,
  templateCode,
  onSelect,
}: {
  unit: CombatUnit & { statuses?: string[]; defending?: boolean; mana?: number; mana_cost?: number }
  isTarget: boolean
  templateCode?: string
  onSelect?: () => void
}) {
  const pct = unit.max_hp > 0 ? Math.max(0, unit.hp / unit.max_hp) : 0
  const [bustOk, setBustOk] = useState(true)
  const bustUrl = templateCode && bustOk ? `${BUST_BASE}${templateCode}.png` : null
  const statusList = [...(unit.statuses ?? [])]
  if (unit.defending && !statusList.includes('DEFENDING')) statusList.unshift('DEFENDING')
  return (
    <div
      data-dead={unit.dead ? 'true' : undefined}
      onClick={isTarget && onSelect ? onSelect : undefined}
      style={{
        padding: '6px 8px',
        border: isTarget ? '2px solid var(--color-accent)' : '1px solid rgba(255,255,255,0.1)',
        borderRadius: 6,
        opacity: unit.dead ? 0.4 : 1,
        cursor: isTarget ? 'pointer' : 'default',
        minWidth: 90,
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(2px)',
      }}
    >
      {bustUrl && (
        <img
          src={bustUrl}
          alt=""
          onError={() => setBustOk(false)}
          style={{
            width: '100%',
            height: 56,
            objectFit: 'cover',
            objectPosition: 'top',
            borderRadius: 4,
            marginBottom: 4,
            background: 'rgba(255,255,255,0.05)',
          }}
        />
      )}
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text)', marginBottom: 3 }}>{unit.name}</div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct * 100}%`, height: '100%', background: unit.dead ? '#666' : 'var(--color-accent)', transition: 'width 0.3s' }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--color-muted)', marginTop: 2 }}>{unit.hp} / {unit.max_hp}</div>
      <StatusStrip statuses={statusList} />
    </div>
  )
}

function ActionBar({ pending, onAct, disabled }: {
  pending: InteractivePending
  onAct: (targetUid: string, actionType?: ActionType) => void
  disabled: boolean
}) {
  const [selectedAction, setSelectedAction] = useState<ActionType>('attack')
  const actions = pending.actions ?? {
    attack: { enabled: true, reason: null },
    skill:  { enabled: !!pending.special_name && (pending.special_cooldown_left ?? 0) === 0, reason: null },
    limit:  { enabled: (pending.limit_gauge ?? 0) >= (pending.limit_gauge_max ?? 100), reason: null },
    defend: { enabled: true, reason: null },
  }

  const handle = (kind: ActionType) => {
    if (disabled || !actions[kind]?.enabled) return
    if (kind === 'defend') { onAct('', 'defend'); return }
    if (kind === 'limit') { onAct('', 'limit'); return }
    if (kind === 'skill' && pending.special_kind && /AOE|HEAL|BUFF|CLEANSE/.test(pending.special_kind)) {
      onAct('', 'skill'); return
    }
    // attack and single-target skills require a target click — arm the bar
    setSelectedAction(kind)
  }

  const Button = ({ kind, label, sub }: { kind: ActionType; label: string; sub?: string }) => {
    const a = actions[kind] ?? { enabled: false, reason: null }
    const armed = selectedAction === kind
    const color = kind === 'limit' ? '#e8a35a' : kind === 'skill' ? '#9b88ff' : kind === 'defend' ? '#5ad8a3' : '#00e0d0'
    return (
      <button
        disabled={!a.enabled || disabled}
        onClick={() => handle(kind)}
        title={a.reason ?? undefined}
        style={{
          flex: 1, padding: '10px 8px',
          background: armed ? `${color}26` : 'rgba(0,0,0,0.6)',
          border: `1px solid ${a.enabled ? `${color}99` : 'rgba(255,255,255,0.12)'}`,
          color: a.enabled ? color : 'rgba(255,255,255,0.32)',
          fontFamily: 'JetBrains Mono, ui-monospace, monospace',
          fontSize: 11, fontWeight: 700, letterSpacing: '0.18em',
          cursor: a.enabled && !disabled ? 'pointer' : 'not-allowed',
          textTransform: 'uppercase', display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 2, borderRadius: 4, transition: 'all 0.12s',
        }}
      >
        <span>{label}</span>
        {sub && <span style={{ fontSize: 9, opacity: 0.75, letterSpacing: '0.08em' }}>{sub}</span>}
      </button>
    )
  }

  const limitPct = pending.limit_gauge_max
    ? Math.min(100, Math.round((pending.limit_gauge ?? 0) / pending.limit_gauge_max * 100))
    : 0

  return (
    <div style={{
      position: 'absolute', bottom: 92, left: '50%', transform: 'translateX(-50%)',
      display: 'flex', flexDirection: 'column', gap: 6, pointerEvents: 'auto',
      minWidth: 480, maxWidth: 640,
    }}>
      <div style={{
        fontFamily: 'JetBrains Mono, ui-monospace, monospace',
        fontSize: 10, letterSpacing: '0.3em', color: 'rgba(255,255,255,0.7)',
        textAlign: 'center', textTransform: 'uppercase',
      }}>
        {pending.actor_name ?? pending.actor_uid} · turn {pending.turn_number ?? '—'}
        {selectedAction === 'attack' && (actions.attack?.enabled || actions.skill?.enabled) && (
          <span style={{ marginLeft: 10, color: '#00e0d0' }}>
            ▸ pick enemy target
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <Button kind="attack" label="Attack" />
        <Button
          kind="skill"
          label={pending.special_name ?? 'Skill'}
          sub={(pending.special_cooldown_left ?? 0) > 0 ? `CD ${pending.special_cooldown_left}` : 'ready'}
        />
        <Button kind="limit" label="Limit" sub={`${limitPct}%`} />
        <Button kind="defend" label="Defend" sub="-50% dmg" />
      </div>
    </div>
  )
}

export function BattleHUD({ teamA, teamB, onAct, pendingActorUid, pending, validTargets, acting, done, rewards, onClose, templateByUid, turnStartedAt, turnTimeoutS, turnOrderPeek }: BattleHUDProps) {
  const validSet = new Set(validTargets)
  const showTimer = !done && turnStartedAt != null && (turnTimeoutS ?? 0) > 0
  const showActionBar = !!pending && !!onAct && !done
  const allUnits = [...teamA, ...teamB]

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', padding: 16 }}>
      {showTimer && <TurnTimer startedAt={turnStartedAt!} timeoutS={turnTimeoutS!} />}
      {!done && turnOrderPeek && turnOrderPeek.length > 0 && (
        <TurnOrderRibbon
          peek={turnOrderPeek}
          units={allUnits}
          templateByUid={templateByUid}
          currentUid={pendingActorUid}
        />
      )}
      {showActionBar && <ActionBar pending={pending!} onAct={onAct!} disabled={acting} />}
      {/* Team A (player) — bottom left */}
      <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', gap: 8, pointerEvents: 'auto' }}>
        {teamA.map(u => (
          <UnitCard
            key={u.uid}
            unit={u}
            isTarget={false}
            templateCode={templateByUid?.[u.uid]}
          />
        ))}
      </div>

      {/* Team B (enemies) — bottom right, compact */}
      <div style={{ position: 'absolute', bottom: 16, right: 16, display: 'flex', gap: 6, pointerEvents: 'auto' }}>
        {teamB.map(u => (
          <UnitCard
            key={u.uid}
            unit={u}
            isTarget={!!onAct && validSet.has(u.uid)}
            templateCode={templateByUid?.[u.uid]}
            onSelect={onAct ? () => onAct(u.uid) : undefined}
          />
        ))}
      </div>

      {/* Rewards overlay */}
      {done && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.75)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          pointerEvents: 'auto',
        }}>
          <div style={{ background: 'var(--color-surface)', borderRadius: 12, padding: 32, textAlign: 'center', minWidth: 260 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--color-text)', marginBottom: 16 }}>Battle Complete</div>
            {rewards && Object.entries(rewards).filter(([, v]) => v > 0).map(([k, v]) => (
              <div key={k} style={{ fontSize: 14, color: 'var(--color-muted)', marginBottom: 4 }}>+{v} {k}</div>
            ))}
            <button
              onClick={onClose}
              style={{ marginTop: 20, padding: '10px 28px', background: 'var(--color-accent)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 700 }}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {acting && (
        <div style={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.7)', color: '#fff', padding: '4px 12px', borderRadius: 4, fontSize: 12, pointerEvents: 'none' }}>
          Acting…
        </div>
      )}
    </div>
  )
}
