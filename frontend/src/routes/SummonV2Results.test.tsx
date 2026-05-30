import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SummonV2ResultsRoute } from './SummonV2Results'

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

const pulledHeroes = [{
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
}]

const pulledOutcomes = [{
  hero: pulledHeroes[0],
  rarity: 'LEGENDARY',
  pulled_epic_pity: false,
  is_duplicate: true,
  shards_granted: 15,
}]

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: mockMe, isLoading: false }),
}))

vi.mock('../api/summon', () => ({
  pullStandard: async () => ({ heroes: pulledHeroes }),
}))

function renderRoute() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[{
          pathname: '/app/summon/results',
          state: { heroes: pulledHeroes, outcomes: pulledOutcomes, pullCount: 1 },
        }]}
      >
        <Routes>
          <Route path="/app/summon/results" element={<SummonV2ResultsRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SummonV2ResultsRoute', () => {
  it('surfaces post-pull impact, shard value, and free repull pressure', () => {
    renderRoute()
    expect(screen.getByText(/Roster Impact/i)).toBeInTheDocument()
    expect(screen.getByText(/Arena Angle/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Check Ascend/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /FREE REPULL x1/i })).toBeInTheDocument()
    expect(screen.getAllByText(/\+15 shards/i)).toHaveLength(2)
  })
})
