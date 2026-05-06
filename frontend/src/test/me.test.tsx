import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { MeRoute } from '../routes/Me'

const mockMe = {
  id: 1, email: 'player@test.com', coins: 1000, gems: 50, shards: 20,
  access_cards: 5, free_summon_credits: 3, energy: 45, energy_cap: 60,
  pulls_since_epic: 12, stages_cleared: ['tutorial_first_ticket'],
  arena_rating: 1050, arena_wins: 5, arena_losses: 3,
  account_level: 4, account_xp: 350, qol_unlocks: {}, active_cosmetic_frame: '',
}

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: mockMe, isLoading: false }),
}))

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
)

describe('MeRoute', () => {
  it('shows account email username', () => {
    render(<MeRoute />, { wrapper })
    // Component shows email.split('@')[0] — full address is never rendered
    expect(screen.getAllByText(/player/).length).toBeGreaterThan(0)
  })

  it('shows coins', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getAllByText(/1,000/).length).toBeGreaterThan(0)
  })

  it('shows account level', () => {
    render(<MeRoute />, { wrapper })
    // Profile banner renders "Lv {level} · {xp} XP" as a single text block
    expect(screen.getByText(/Lv\s+4/)).toBeInTheDocument()
  })
})
