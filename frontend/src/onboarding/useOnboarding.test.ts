import { describe, it, expect, beforeEach } from 'vitest'
import { useShouldOnboard, markOnboardingSeen, replayOnboarding } from './useOnboarding'

describe('useOnboarding gate', () => {
  beforeEach(() => localStorage.clear())

  it('shows for a fresh level-1 account', () => {
    expect(useShouldOnboard(1)).toBe(true)
  })

  it('hides once marked seen', () => {
    markOnboardingSeen()
    expect(useShouldOnboard(1)).toBe(false)
  })

  it('hides for higher-level accounts even if unseen', () => {
    expect(useShouldOnboard(5)).toBe(false)
  })

  it('hides when account level is undefined (me not loaded)', () => {
    expect(useShouldOnboard(undefined)).toBe(false)
  })

  it('replayOnboarding re-enables it', () => {
    markOnboardingSeen()
    expect(useShouldOnboard(1)).toBe(false)
    replayOnboarding()
    expect(useShouldOnboard(1)).toBe(true)
  })
})
