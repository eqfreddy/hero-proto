import { act, render, screen } from '@testing-library/react'
import { SummonRevealOverlay } from './SummonRevealOverlay'

const hero = {
  id: 7,
  template: {
    id: 7,
    code: 'the_consultant',
    name: 'The Consultant',
    rarity: 'LEGENDARY' as const,
    role: 'ATK' as const,
    faction: 'EXILE' as const,
    attack_kind: 'melee' as const,
    base_hp: 1,
    base_atk: 1,
    base_def: 1,
    base_spd: 1,
  },
  level: 30,
  stars: 5,
  special_level: 3,
  power: 8200,
  hp: 1,
  atk: 1,
  def: 1,
  spd: 1,
  has_variance: false,
  variance_net: 0,
  dupe_count: 1,
  instance_ids: [7],
}

describe('SummonRevealOverlay', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('steps through the commander briefing and unlocks continue', () => {
    const onContinue = vi.fn()

    render(<SummonRevealOverlay heroes={[hero]} pullCount={1} onContinue={onContinue} />)

    expect(screen.getByText(/Incoming recruit signal/i)).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(1300)
    })
    expect(screen.getByText(/Threat classification/i)).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(1600)
    })
    const continueButton = screen.getByRole('button', { name: /Continue To Dossier/i })
    expect(continueButton).toBeInTheDocument()

    continueButton.click()
    expect(onContinue).toHaveBeenCalledTimes(1)
  })
})
