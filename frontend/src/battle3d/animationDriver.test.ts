import { describe, it, expect } from 'vitest'
import { handleEvent } from './animationDriver'
import type { UnitRig } from './animationDriver'

function fakeRig(uid: string): UnitRig & { calls: string[] } {
  const calls: string[] = []
  return {
    uid, archetype: 'knight', availableClips: ['hit', 'die'], calls,
    play: (c: string) => calls.push(`play:${c}`),
    flashWhite: () => calls.push('flashWhite'),
    floatDamageNumber: () => calls.push('float'),
    floatQuip: (line: string) => calls.push(`quip:${line}`),
    fade: (o: number) => calls.push(`fade:${o}`),
  }
}

describe('handleEvent — system integrity', () => {
  it('CRASH staggers and flashes the target', () => {
    const rig = fakeRig('B0')
    const rigs = new Map<string, UnitRig>([['B0', rig]])
    handleEvent({ type: 'CRASH', unit: 'B0' }, rigs)
    expect(rig.calls).toContain('flashWhite')
  })

  it('DELETED fades the target out', () => {
    const rig = fakeRig('B0')
    const rigs = new Map<string, UnitRig>([['B0', rig]])
    handleEvent({ type: 'DELETED', source: 'A0', target: 'B0' }, rigs)
    expect(rig.calls.some((c) => c.startsWith('fade:'))).toBe(true)
  })
})
