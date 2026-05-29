import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SummonV2Route } from './SummonV2'

const mockMe = {
  id: 1,
  email: 'money@test.com',
  coins: 1200,
  gems: 40,
  shards: 17,
  access_cards: 5,
  free_summon_credits: 1,
  energy: 60,
  energy_cap: 100,
  energy_next_tick_in: 0,
  arena_tickets: 5,
  arena_tickets_cap: 5,
  arena_tickets_next_tick_in: 0,
  arena_weekly_wins: 0,
  pending_arena_rewards: [],
  pulls_since_epic: 43,
  stages_cleared: ['tutorial_first_ticket'],
  arena_rating: 1780,
  arena_wins: 24,
  arena_losses: 9,
  account_level: 18,
  account_xp: 0,
  qol_unlocks: {},
  active_cosmetic_frame: '',
  faction: 'EXILE' as const,
  alignment_chosen_at: null,
  email_verified: true,
  totp_enabled: false,
  is_admin: false,
}

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: mockMe, isLoading: false }),
}))

vi.mock('../hooks/useHeroes', () => ({
  useHeroes: () => ({
    data: [{
      id: 7,
      template: {
        id: 7,
        code: 'the_consultant',
        name: 'The Consultant',
        rarity: 'LEGENDARY',
        role: 'ATK',
        faction: 'EXILE',
        attack_kind: 'melee',
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
    }],
    isLoading: false,
  }),
}))

vi.mock('../api/summon', () => ({
  pullStandard: async () => ({ heroes: [], outcomes: [] }),
}))

vi.mock('../api/friendPoints', () => ({
  fetchFriendPoints: async () => ({
    balance: 320,
    fp_per_summon: 100,
    fp_pulls_since_epic: 9,
    fp_pity_threshold: 50,
  }),
  summonFriendBanner: async () => ({ hero: null }),
}))

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
)

describe('SummonV2Route', () => {
  it('surfaces competitive chase pressure on the standard banner', async () => {
    render(<SummonV2Route />, { wrapper })
    expect(await screen.findByText(/Meta Pressure/i)).toBeInTheDocument()
    expect(screen.getByText(/1 free pull is loaded/i)).toBeInTheDocument()
    expect(screen.getByText(/43\/50 pity/i)).toBeInTheDocument()
    expect(screen.getByText(/arena edge/i)).toBeInTheDocument()
    expect(screen.getByText(/One premium carry only/i)).toBeInTheDocument()
    expect(screen.getByText(/Soft pity online/i)).toBeInTheDocument()
  })
})
