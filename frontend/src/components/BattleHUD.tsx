import { useEffect, useState } from 'react'
import type { CombatUnit, InteractivePending } from '../types/battle'
import type { ActionType } from '../api/battles'
import { assetUrl } from '../api/client'

const PORTRAIT_BASE = '/app/static/heroes/'
const BUST_BASE = '/app/static/heroes/busts/'
const PLACEHOLDER_BASE = '/app/placeholder/hero/'

interface BattleHUDProps {
  teamA: CombatUnit[]
  teamB: CombatUnit[]
  onAct: ((targetUid: string, actionType?: ActionType) => void) | undefined
  onSelectAction?: ((actionType: ActionType) => void) | undefined
  pendingActorUid: string | null
  pending?: InteractivePending | null
  selectedAction?: ActionType
  validTargets: string[]
  acting: boolean
  done: boolean
  rewards: Record<string, unknown> | null
  onClose: () => void
  templateByUid?: Record<string, string>
  turnStartedAt?: number | null
  turnTimeoutS?: number
  turnOrderPeek?: string[]
}

function PortraitFallback({
  templateCode,
  title,
}: {
  templateCode?: string
  title: string
}) {
  const [stage, setStage] = useState<'portrait' | 'bust' | 'placeholder' | 'initial'>('portrait')
  if (!templateCode || stage === 'initial') {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        display: 'grid',
        placeItems: 'center',
        fontSize: 12,
        fontWeight: 700,
        color: '#cfd6dd',
      }}>
        {title.slice(0, 1)}
      </div>
    )
  }

  const src = stage === 'portrait'
    ? assetUrl(`${PORTRAIT_BASE}${templateCode}.svg`)
    : stage === 'bust'
      ? assetUrl(`${BUST_BASE}${templateCode}.png`)
      : `${PLACEHOLDER_BASE}${templateCode}.svg`

  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      onError={() => {
        setStage((prev) => {
          if (prev === 'portrait') return 'bust'
          if (prev === 'bust') return 'placeholder'
          return 'initial'
        })
      }}
      style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }}
    />
  )
}

function TurnOrderRibbon({ peek, units, templateByUid, currentUid }: {
  peek: string[]
  units: CombatUnit[]
  templateByUid?: Record<string, string>
  currentUid?: string | null
}) {
  if (!peek || peek.length === 0) return null
  const byUid = new Map(units.map((u) => [u.uid, u]))
  return (
    <div style={{
      position: 'absolute',
      top: 56,
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      gap: 4,
      pointerEvents: 'none',
      background: 'rgba(0,0,0,0.45)',
      borderRadius: 6,
      padding: '4px 6px',
      border: '1px solid rgba(255,255,255,0.08)',
    }}>
      {peek.map((uid, i) => {
        const u = byUid.get(uid)
        if (!u) return null
        const isCurrent = uid === currentUid && i === 0
        const sideRing = (u.side ?? (uid.startsWith('a') ? 'A' : 'B')) === 'A' ? '#00e0d0' : '#ff5a78'
        const size = i === 0 ? 36 : 28
        return (
          <div
            key={`${uid}-${i}`}
            title={`${u.name}${isCurrent ? ' · NOW' : i === 1 ? ' · next' : ''}`}
            style={{
              position: 'relative',
              width: size,
              height: size,
              borderRadius: 4,
              overflow: 'hidden',
              border: `1.5px solid ${isCurrent ? '#ffd86b' : sideRing}`,
              background: 'rgba(0,0,0,0.55)',
              opacity: u.dead ? 0.3 : 1 - i * 0.08,
              boxShadow: isCurrent ? '0 0 12px rgba(255,216,107,0.55)' : 'none',
            }}
          >
            <PortraitFallback templateCode={templateByUid?.[uid]} title={u.name} />
          </div>
        )
      })}
    </div>
  )
}

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
      position: 'absolute',
      top: 12,
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'rgba(0,0,0,0.65)',
      border: `1px solid ${color}`,
      borderRadius: 16,
      padding: '4px 14px',
      fontSize: 13,
      fontWeight: 800,
      color,
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      pointerEvents: 'none',
      letterSpacing: 0.5,
      fontVariantNumeric: 'tabular-nums',
    }}>
      <span>⏱</span>
      <span>{remaining}s</span>
      {critical && <span style={{ fontSize: 10, opacity: 0.85, marginLeft: 4 }}>FORFEIT IMMINENT</span>}
    </div>
  )
}

const STATUS_META: Record<string, { icon?: string; color: string; label: string; asset?: string }> = {
  POISON: { color: '#9ee37d', label: 'Poison', asset: '/app/static/status/POISON.svg' },
  BURN: { icon: '🔥', color: '#ff8c5a', label: 'Burn' },
  STUN: { color: '#ffd86b', label: 'Stun', asset: '/app/static/status/STUN.svg' },
  FREEZE: { icon: '❄', color: '#7fd8ff', label: 'Freeze' },
  SHIELD: { color: '#a8c4ff', label: 'Shield', asset: '/app/static/status/SHIELD.svg' },
  REFLECT: { icon: '↺', color: '#d8a8ff', label: 'Reflect' },
  HEAL_BLOCK: { icon: '✕', color: '#ff7da3', label: 'Heal Block' },
  ATK_UP: { color: '#ff8c8c', label: 'ATK Up', asset: '/app/static/status/ATK_UP.svg' },
  DEF_DOWN: { color: '#8c8cff', label: 'DEF Down', asset: '/app/static/status/DEF_DOWN.svg' },
  DEFENDING: { icon: '🛡', color: '#a8c4ff', label: 'Defending' },
}

function StatusStrip({ statuses }: { statuses?: string[] }) {
  if (!statuses?.length) return null
  return (
    <div style={{ display: 'flex', gap: 3, marginTop: 3, flexWrap: 'wrap' }}>
      {statuses.slice(0, 5).map((status) => {
        const meta = STATUS_META[status] ?? { icon: '·', color: '#aaa', label: status }
        return (
          <span
            key={status}
            title={meta.label}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              minWidth: 18,
              minHeight: 18,
              borderRadius: 2,
              background: 'rgba(0,0,0,0.55)',
              color: meta.color,
              fontSize: 10,
              fontWeight: 700,
              lineHeight: 1,
              padding: '1px 3px',
            }}
          >
            {meta.asset ? (
              <img src={assetUrl(meta.asset)} alt="" aria-hidden="true" style={{ width: 12, height: 12 }} />
            ) : (
              meta.icon
            )}
          </span>
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
      <div style={{
        width: '100%',
        height: 56,
        borderRadius: 4,
        marginBottom: 4,
        background: 'rgba(255,255,255,0.05)',
        overflow: 'hidden',
      }}>
        <PortraitFallback templateCode={templateCode} title={unit.name} />
      </div>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text)', marginBottom: 3 }}>{unit.name}</div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
        <div
          style={{
            width: `${pct * 100}%`,
            height: '100%',
            background: unit.dead ? '#666' : 'var(--color-accent)',
            transition: 'width 0.3s',
          }}
        />
      </div>
      <div style={{ fontSize: 10, color: 'var(--color-muted)', marginTop: 2 }}>{unit.hp} / {unit.max_hp}</div>
      {(unit.integrity_max ?? 0) > 0 && (
        <div data-testid={`integrity-${unit.uid}`} style={{ marginTop: 3 }}>
          <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
            <div
              style={{
                width: `${Math.max(0, Math.min(1, (unit.integrity ?? 0) / (unit.integrity_max || 1))) * 100}%`,
                height: '100%',
                background: unit.crashed ? '#e85a78' : '#5ad8ff',
                transition: 'width 0.3s',
              }}
            />
          </div>
          <div style={{ fontSize: 9, color: 'var(--color-muted)', letterSpacing: '0.12em', marginTop: 1 }}>
            {unit.crashed ? 'CRASHED' : 'INTEGRITY'}
          </div>
        </div>
      )}
      {(unit.burnout ?? 0) > 0 && (
        <div data-testid={`burnout-${unit.uid}`} style={{ marginTop: 3 }}>
          <div style={{ height: 3, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
            <div
              style={{
                width: `${Math.max(0, Math.min(100, unit.burnout ?? 0))}%`,
                height: '100%',
                background:
                  (unit.burnout ?? 0) >= 75 ? '#ff5a4d'
                  : (unit.burnout ?? 0) <= 25 ? '#5ad8a3'
                  : '#e8a35a',
                transition: 'width 0.3s',
              }}
            />
          </div>
        </div>
      )}
      <StatusStrip statuses={statusList} />
    </div>
  )
}

function ActionBar({ pending, onAct, onSelectAction, disabled, selectedAction }: {
  pending: InteractivePending
  onAct: (targetUid: string, actionType?: ActionType) => void
  onSelectAction?: (actionType: ActionType) => void
  disabled: boolean
  selectedAction: ActionType
}) {
  const actions = pending.actions ?? {
    attack: { enabled: true, reason: null },
    skill: { enabled: !!pending.special_name && (pending.special_cooldown_left ?? 0) === 0, reason: null },
    limit: { enabled: (pending.limit_gauge ?? 0) >= (pending.limit_gauge_max ?? 100), reason: null },
    defend: { enabled: true, reason: null },
    delete: { enabled: false, reason: null },
  }
  const skillNeedsTarget = !!(pending.special_kind && !/AOE|HEAL|BUFF|CLEANSE/.test(pending.special_kind))
  const selectedActionLabel =
    selectedAction === 'skill' ? (pending.special_name ?? 'Skill') :
      selectedAction === 'limit' ? 'Limit' :
        selectedAction === 'defend' ? 'Defend' :
          'Attack'

  const handle = (kind: ActionType) => {
    if (disabled || !actions[kind]?.enabled) return
    if (kind === 'defend') { onAct('', 'defend'); return }
    if (kind === 'limit') { onAct('', 'limit'); return }
    if (kind === 'skill' && !skillNeedsTarget) {
      onAct('', 'skill')
      return
    }
    onSelectAction?.(kind)
  }

  const Button = ({ kind, label, sub }: { kind: ActionType; label: string; sub?: string }) => {
    const action = actions[kind] ?? { enabled: false, reason: null }
    const armed = selectedAction === kind
    const color = kind === 'limit' ? '#e8a35a' : kind === 'skill' ? '#9b88ff' : kind === 'defend' ? '#5ad8a3' : '#00e0d0'
    return (
      <button
        disabled={!action.enabled || disabled}
        onClick={() => handle(kind)}
        title={action.reason ?? undefined}
        style={{
          flex: 1,
          padding: '10px 8px',
          background: armed ? `${color}26` : 'rgba(0,0,0,0.6)',
          border: `1px solid ${action.enabled ? `${color}99` : 'rgba(255,255,255,0.12)'}`,
          color: action.enabled ? color : 'rgba(255,255,255,0.32)',
          fontFamily: 'JetBrains Mono, ui-monospace, monospace',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.18em',
          cursor: action.enabled && !disabled ? 'pointer' : 'not-allowed',
          textTransform: 'uppercase',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
          borderRadius: 4,
          transition: 'background-color 0.18s, border-color 0.18s, color 0.18s',
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
      position: 'absolute',
      bottom: 110,
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      pointerEvents: 'auto',
      width: 'min(92vw, 640px)',
    }}>
      <div style={{
        fontFamily: 'JetBrains Mono, ui-monospace, monospace',
        fontSize: 10,
        letterSpacing: '0.3em',
        color: 'rgba(255,255,255,0.7)',
        textAlign: 'center',
        textTransform: 'uppercase',
      }}>
        {pending.actor_name ?? pending.actor_uid} · turn {pending.turn_number ?? '—'}
        {(selectedAction === 'attack' || (selectedAction === 'skill' && skillNeedsTarget)) && (
          <span style={{ marginLeft: 10, color: '#00e0d0' }}>
            ▸ pick enemy target for {selectedActionLabel}
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
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
        gap: 6,
        fontFamily: 'JetBrains Mono, ui-monospace, monospace',
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
      }}>
        <div style={{
          padding: '6px 8px',
          borderRadius: 4,
          background: 'rgba(0,0,0,0.55)',
          border: '1px solid rgba(90,216,163,0.25)',
          color: '#5ad8a3',
          textAlign: 'center',
        }}>
          MP {pending.mana ?? 0}/{Math.max((pending.mana_cost ?? 0) * 5, pending.mana ?? 0, 0)}
        </div>
        <div style={{
          padding: '6px 8px',
          borderRadius: 4,
          background: 'rgba(0,0,0,0.55)',
          border: '1px solid rgba(232,163,90,0.25)',
          color: '#e8a35a',
          textAlign: 'center',
        }}>
          LB {pending.limit_gauge ?? 0}/{pending.limit_gauge_max ?? 100}
        </div>
        <div style={{
          padding: '6px 8px',
          borderRadius: 4,
          background: 'rgba(0,0,0,0.55)',
          border: '1px solid rgba(155,136,255,0.25)',
          color: '#cbbdff',
          textAlign: 'center',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {pending.special_name ?? 'No Skill'}
        </div>
      </div>
    </div>
  )
}

function rewardLines(rewards: Record<string, unknown> | null): string[] {
  if (!rewards) return []
  const lines: string[] = []
  for (const [key, value] of Object.entries(rewards)) {
    if (key.startsWith('_') || key === 'completed_daily_quest_ids' || key === 'milestone_unlocks') continue
    if (typeof value === 'number') {
      if (value > 0) lines.push(`+${value.toLocaleString()} ${key}`)
      continue
    }
    if (key === 'gear' && value && typeof value === 'object') {
      const gear = value as Record<string, unknown>
      const rarity = String(gear.rarity ?? '').replace(/^Rarity\./, '')
      const slot = String(gear.slot ?? '').replace(/^GearSlot\./, '')
      const mailed = gear.mailboxed ? ' mailed' : ''
      if (rarity || slot) lines.push(`${rarity} ${slot} gear${mailed}`.trim())
      continue
    }
    if (key === 'materials' && Array.isArray(value)) {
      for (const material of value) {
        if (!material || typeof material !== 'object') continue
        const row = material as Record<string, unknown>
        const qty = Number(row.qty ?? 0)
        const code = String(row.code ?? 'material')
        if (qty > 0) lines.push(`+${qty.toLocaleString()} ${code}`)
      }
      continue
    }
    if (key === 'collection_drop' && value && typeof value === 'object') {
      const drop = value as Record<string, unknown>
      lines.push(`Collection piece: ${String(drop.name ?? drop.piece_code ?? 'new piece')}`)
    }
  }
  return lines
}

export function BattleHUD({
  teamA,
  teamB,
  onAct,
  onSelectAction,
  pendingActorUid,
  pending,
  selectedAction: controlledSelectedAction,
  validTargets,
  acting,
  done,
  rewards,
  onClose,
  templateByUid,
  turnStartedAt,
  turnTimeoutS,
  turnOrderPeek,
}: BattleHUDProps) {
  const [localSelectedAction, setLocalSelectedAction] = useState<ActionType>('attack')
  const validSet = new Set(validTargets)
  const showTimer = !done && turnStartedAt != null && (turnTimeoutS ?? 0) > 0
  const showActionBar = !!pending && !!onAct && !done
  const allUnits = [...teamA, ...teamB]
  const selectedAction = controlledSelectedAction ?? localSelectedAction
  const rewardText = rewardLines(rewards)

  useEffect(() => {
    if (!pending) return
    setLocalSelectedAction('attack')
  }, [pending?.actor_uid, pending?.turn_number])

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
      {showActionBar && (
        <ActionBar
          pending={pending!}
          onAct={onAct!}
          onSelectAction={(actionType) => {
            setLocalSelectedAction(actionType)
            onSelectAction?.(actionType)
          }}
          disabled={acting}
          selectedAction={selectedAction}
        />
      )}

      <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', gap: 8, pointerEvents: 'auto' }}>
        {teamA.map((unit) => (
          <UnitCard
            key={unit.uid}
            unit={unit}
            isTarget={false}
            templateCode={templateByUid?.[unit.uid]}
          />
        ))}
      </div>

      <div style={{ position: 'absolute', bottom: 16, right: 16, display: 'flex', gap: 6, pointerEvents: 'auto' }}>
        {teamB.map((unit) => (
          <UnitCard
            key={unit.uid}
            unit={unit}
            isTarget={!!onAct && validSet.has(unit.uid)}
            templateCode={templateByUid?.[unit.uid]}
            onSelect={onAct ? () => onAct(unit.uid, selectedAction) : undefined}
          />
        ))}
      </div>

      {done && (
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,0.75)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'auto',
        }}>
          <div style={{ background: 'var(--color-surface)', borderRadius: 12, padding: 32, textAlign: 'center', minWidth: 260 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--color-text)', marginBottom: 8 }}>Battle Complete</div>
            {rewardText.length > 0 ? rewardText.map((line) => (
              <div key={line} style={{ fontSize: 14, color: 'var(--color-muted)', marginBottom: 4 }}>{line}</div>
            )) : (
              <div style={{ fontSize: 14, color: 'var(--color-muted)', marginBottom: 4 }}>
                No loot this time. Run it back.
              </div>
            )}
            <button
              onClick={onClose}
              style={{
                marginTop: 20,
                padding: '10px 28px',
                background: 'var(--color-accent)',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {acting && (
        <div style={{
          position: 'absolute',
          top: 8,
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.7)',
          color: '#fff',
          padding: '4px 12px',
          borderRadius: 4,
          fontSize: 12,
          pointerEvents: 'none',
        }}>
          Acting…
        </div>
      )}
    </div>
  )
}
