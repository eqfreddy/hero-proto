import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BattleHUD } from './BattleHUD'
import type { CombatUnit } from '../types/battle'

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
})
