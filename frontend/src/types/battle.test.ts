import { describe, it, expect } from 'vitest'
import type { CombatUnit, InteractivePending } from './battle'
import type { ActionType } from '../api/battles'

describe('System Integrity types', () => {
  it('CombatUnit carries integrity/burnout/crashed', () => {
    const u: CombatUnit = {
      uid: 'B0', name: 'e', hp: 100, max_hp: 100, atk: 1, def: 1, spd: 1, dead: false,
      integrity: 0, integrity_max: 150, burnout: 40, crashed: true,
    }
    expect(u.integrity_max).toBe(150)
    expect(u.crashed).toBe(true)
    expect(u.burnout).toBe(40)
  })

  it('InteractivePending exposes valid_delete_targets and a delete action', () => {
    const p: InteractivePending = {
      actor_uid: 'A0',
      valid_delete_targets: ['B0'],
      actions: {
        attack: { enabled: true, reason: null },
        skill: { enabled: false, reason: 'on cooldown' },
        limit: { enabled: false, reason: 'gauge not full' },
        defend: { enabled: true, reason: null },
        delete: { enabled: true, reason: null },
      },
    }
    expect(p.valid_delete_targets).toEqual(['B0'])
    expect(p.actions?.delete.enabled).toBe(true)
  })

  it('ActionType includes delete', () => {
    const a: ActionType = 'delete'
    expect(a).toBe('delete')
  })
})
