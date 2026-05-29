import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { BattleHUD } from './BattleHUD'
import type { CombatUnit, InteractivePending } from '../types/battle'

const makeUnit = (uid: string, hp: number, max_hp: number, dead = false): CombatUnit => ({
  uid, name: uid, hp, max_hp, atk: 100, def: 50, spd: 10, dead,
})

describe('BattleHUD', () => {
  it('renders unit name and hp bar', () => {
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[makeUnit('enemy-1', 60, 120)]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />
    )
    expect(screen.getByText('hero-1')).toBeTruthy()
    expect(screen.getByText('enemy-1')).toBeTruthy()
  })

  it('marks dead units', () => {
    render(
      <BattleHUD
        teamA={[makeUnit('dead-hero', 0, 100, true)]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />
    )
    expect(screen.getByText('dead-hero').closest('[data-dead]')).toBeTruthy()
  })

  it('shows rewards overlay when done=true', () => {
    render(
      <BattleHUD
        teamA={[]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={true}
        rewards={{ coins: 150, gems: 0, shards: 1 }}
        onClose={() => {}}
      />
    )
    expect(screen.getByText(/150/)).toBeTruthy()
  })

  it('sends the armed single-target skill action when an enemy is clicked', () => {
    const onAct = vi.fn()
    const pending: InteractivePending = {
      actor_uid: 'hero-1',
      actor_name: 'hero-1',
      turn_number: 3,
      enemies: [{ uid: 'enemy-1', name: 'enemy-1', hp: 60, max_hp: 120 }],
      actions: {
        attack: { enabled: true, reason: null },
        skill: { enabled: true, reason: null },
        limit: { enabled: false, reason: 'gauge not full' },
        defend: { enabled: true, reason: null },
        delete: { enabled: false, reason: null },
      },
      special_name: 'Rollback',
      special_kind: 'DAMAGE',
      special_cooldown_left: 0,
      mana: 50,
      mana_cost: 20,
      limit_gauge: 30,
      limit_gauge_max: 100,
    }

    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[makeUnit('enemy-1', 60, 120)]}
        onAct={onAct}
        pendingActorUid="hero-1"
        pending={pending}
        validTargets={['enemy-1']}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /rollback/i }))
    fireEvent.click(screen.getByText('enemy-1'))

    expect(onAct).toHaveBeenCalledWith('enemy-1', 'skill')
  })

  it('fires defend immediately without requiring a target click', () => {
    const onAct = vi.fn()
    const pending: InteractivePending = {
      actor_uid: 'hero-1',
      actor_name: 'hero-1',
      turn_number: 3,
      enemies: [{ uid: 'enemy-1', name: 'enemy-1', hp: 60, max_hp: 120 }],
      actions: {
        attack: { enabled: true, reason: null },
        skill: { enabled: false, reason: 'on cooldown' },
        limit: { enabled: false, reason: 'gauge not full' },
        defend: { enabled: true, reason: null },
        delete: { enabled: false, reason: null },
      },
      special_name: 'Rollback',
      special_kind: 'DAMAGE',
      special_cooldown_left: 2,
      mana: 50,
      mana_cost: 20,
      limit_gauge: 30,
      limit_gauge_max: 100,
    }

    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[makeUnit('enemy-1', 60, 120)]}
        onAct={onAct}
        pendingActorUid="hero-1"
        pending={pending}
        validTargets={['enemy-1']}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /defend/i }))

    expect(onAct).toHaveBeenCalledWith('', 'defend')
  })

  it('renders an integrity bar for enemies with a bar and a burnout meter', () => {
    const enemy: CombatUnit = {
      uid: 'enemy-1', name: 'enemy-1', hp: 60, max_hp: 120, atk: 1, def: 1, spd: 1,
      dead: false, integrity: 75, integrity_max: 150, burnout: 80,
    }
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[enemy]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />,
    )
    expect(screen.getByTestId('integrity-enemy-1')).toBeTruthy()
    expect(screen.getByTestId('burnout-enemy-1')).toBeTruthy()
  })

  it('omits the integrity bar for heroes (integrity_max 0)', () => {
    render(
      <BattleHUD
        teamA={[makeUnit('hero-1', 80, 100)]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={false}
        rewards={null}
        onClose={() => {}}
      />,
    )
    expect(screen.queryByTestId('integrity-hero-1')).toBeNull()
  })
})
