import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { MeRoute } from '../routes/Me'

const mockMe = {
  id: 1, email: 'player@test.com', coins: 1000, gems: 50, shards: 20,
  access_cards: 5, free_summon_credits: 3, energy: 45, energy_cap: 60,
  energy_next_tick_in: 0, arena_tickets: 5, arena_tickets_cap: 5,
  arena_tickets_next_tick_in: 0, arena_weekly_wins: 0, pending_arena_rewards: [],
  pulls_since_epic: 12, stages_cleared: ['tutorial_first_ticket'],
  arena_rating: 1050, arena_wins: 5, arena_losses: 3,
  account_level: 4, account_xp: 350, qol_unlocks: {}, active_cosmetic_frame: '',
  faction: 'EXILE' as const, alignment_chosen_at: null, email_verified: true, totp_enabled: false, is_admin: false,
}

vi.mock('../hooks/useHeroes', () => ({
  useHeroes: () => ({ data: [], isLoading: false }),
}))

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: mockMe, isLoading: false }),
}))

vi.mock('../api/daily', () => ({
  fetchDaily: async () => [],
}))

vi.mock('../api/shop', () => ({
  fetchShop: async () => ({
    products: [
      {
        sku: 'weekly_bundle',
        title: 'Weekly Ops Kit',
        description: '700 gems + 40 shards + 3 access cards. Resets weekly.',
        kind: 'WEEKLY_BUNDLE',
        price_cents: 999,
        currency_code: 'USD',
        contents: { gems: 700, shards: 40, access_cards: 3 },
        has_stripe: true,
      },
      {
        sku: 'shards_pack',
        title: 'Summoning Cache',
        description: '150 shards - enough for a 10-pull.',
        kind: 'SHARD_PACK',
        price_cents: 999,
        currency_code: 'USD',
        contents: { shards: 150 },
        has_stripe: true,
      },
      {
        sku: 'coin_chest',
        title: 'Coin Chest',
        description: '25,000 coins.',
        kind: 'COIN_PACK',
        price_cents: 99,
        currency_code: 'USD',
        contents: { coins: 25000 },
        has_stripe: true,
      },
      {
        sku: 'qol_auto_battle',
        title: 'QoL: Auto-Battle',
        description: 'Skip the watch.',
        kind: 'SEASONAL_BUNDLE',
        price_cents: 499,
        currency_code: 'USD',
        contents: { qol_unlocks: ['auto_battle'] },
        has_stripe: true,
      },
    ],
    starter: {
      sku: 'starter_pack',
      title: 'Starter Pack',
      description: '500 gems, 100 shards, 5 access cards.',
      kind: 'STARTER_BUNDLE',
      price_cents: 199,
      currency_code: 'USD',
      contents: { gems: 500, shards: 100, access_cards: 5 },
      has_stripe: true,
    },
    history: [],
    shard_exchange: {
      gems_per_batch: 50,
      shards_per_batch: 75,
      max_per_day: 3,
      used_today: 0,
      remaining_today: 3,
    },
  }),
  buyProduct: async () => ({ granted: {} }),
  exchangeShards: async () => ({ shards_granted: 75 }),
}))

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
)

describe('MeRoute', () => {
  it('shows account email username', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getAllByText(/player/).length).toBeGreaterThan(0)
  })

  it('shows command matrix actions', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getByText(/Command Matrix/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Summon/i).length).toBeGreaterThan(0)
  })

  it('shows account level', () => {
    render(<MeRoute />, { wrapper })
    expect(screen.getByText(/Lv\s+4/)).toBeInTheDocument()
  })

  it('surfaces featured conversion hooks instead of placeholder shop copy', async () => {
    render(<MeRoute />, { wrapper })
    expect(await screen.findByText(/Featured Conversion/i)).toBeInTheDocument()
    expect(screen.getByText(/Pressure Points/i)).toBeInTheDocument()
    expect(screen.queryByText(/Coin shop coming soon/i)).not.toBeInTheDocument()
  })
})
