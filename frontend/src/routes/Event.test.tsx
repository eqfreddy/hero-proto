import { render, screen } from '@testing-library/react'
import { EventRoute } from './Event'

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useQuery: () => ({
    data: {
      id: 'ops-breach',
      display_name: 'Ops Breach',
      currency_name: 'Breach Chips',
      currency_emoji: 'CHIP',
      currency_balance: 145,
      ends_at: '2099-01-01T00:00:00Z',
      quests: [
        { code: 'clear-1', title: 'Clear 3 stages', goal: 3, progress: 3, currency_reward: 20, completed: true, claimed: false },
        { code: 'raid-1', title: 'Land a raid hit', goal: 1, progress: 1, currency_reward: 30, completed: true, claimed: true },
      ],
      milestones: [
        { idx: 1, title: 'Cache Bundle', cost: 100, contents: {}, redeemed: false, affordable: true },
        { idx: 2, title: 'Signal Pack', cost: 180, contents: {}, redeemed: false, affordable: false },
      ],
    },
    isLoading: false,
  }),
}))

vi.mock('../store/ui', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('EventRoute', () => {
  it('surfaces event pressure, quests, and milestone progress', () => {
    render(<EventRoute />)

    expect(screen.getByText(/ops breach/i)).toBeInTheDocument()
    expect(screen.getByText(/1\/2/i)).toBeInTheDocument()
    expect(screen.getByText(/1 redeemable/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /redeem/i })).toBeInTheDocument()
    expect(screen.getByText(/need 35/i)).toBeInTheDocument()
    expect(screen.getByText(/145/i)).toBeInTheDocument()
  })
})
