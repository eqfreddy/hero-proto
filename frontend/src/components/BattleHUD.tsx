import type { CombatUnit } from '../types/battle'

interface BattleHUDProps {
  teamA: CombatUnit[]
  teamB: CombatUnit[]
  onAct: ((targetUid: string) => void) | undefined
  pendingActorUid: string | null
  validTargets: string[]
  acting: boolean
  done: boolean
  rewards: Record<string, number> | null
  onClose: () => void
}

function UnitCard({ unit, isTarget, onSelect }: { unit: CombatUnit; isTarget: boolean; onSelect?: () => void }) {
  const pct = unit.max_hp > 0 ? Math.max(0, unit.hp / unit.max_hp) : 0
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
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text)', marginBottom: 3 }}>{unit.name}</div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct * 100}%`, height: '100%', background: unit.dead ? '#666' : 'var(--color-accent)', transition: 'width 0.3s' }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--color-muted)', marginTop: 2 }}>{unit.hp} / {unit.max_hp}</div>
    </div>
  )
}

export function BattleHUD({ teamA, teamB, onAct, pendingActorUid: _pendingActorUid, validTargets, acting, done, rewards, onClose }: BattleHUDProps) {
  const validSet = new Set(validTargets)

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: 16 }}>
      {/* Team B (enemies) — top */}
      <div style={{ display: 'flex', gap: 8, pointerEvents: 'auto' }}>
        {teamB.map(u => (
          <UnitCard
            key={u.uid}
            unit={u}
            isTarget={!!onAct && validSet.has(u.uid)}
            onSelect={onAct ? () => onAct(u.uid) : undefined}
          />
        ))}
      </div>

      {/* Team A (player) — bottom */}
      <div style={{ display: 'flex', gap: 8, pointerEvents: 'auto' }}>
        {teamA.map(u => (
          <UnitCard
            key={u.uid}
            unit={u}
            isTarget={false}
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
