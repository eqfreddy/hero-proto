import { render, screen } from '@testing-library/react'
import { LobbyRoute } from './Lobby'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    NavLink: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    useNavigate: () => vi.fn(),
  }
})

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({
    data: {
      id: 1,
      email: 'player@test.com',
      coins: 0,
      gems: 0,
      shards: 0,
      access_cards: 0,
      free_summon_credits: 0,
      energy: 0,
      energy_cap: 0,
      energy_next_tick_in: 0,
      arena_tickets: 0,
      arena_tickets_cap: 0,
      arena_tickets_next_tick_in: 0,
      arena_weekly_wins: 0,
      pending_arena_rewards: [],
      pulls_since_epic: 0,
      stages_cleared: [],
      arena_rating: 1200,
      arena_wins: 0,
      arena_losses: 0,
      account_level: 20,
      account_xp: 0,
      qol_unlocks: {},
      active_cosmetic_frame: '',
      faction: 'EXILE',
      alignment_chosen_at: null,
      email_verified: true,
      totp_enabled: false,
      is_admin: false,
      rest_xp_banked_seconds: 0,
      eight_tracks: 0,
      win_streak_days: 0,
    },
  }),
}))

vi.mock('../hooks/useHeroes', () => ({
  useHeroes: () => ({ data: [] }),
}))

vi.mock('../hooks/useStages', () => ({
  useStages: () => ({
    data: [{
      id: 1,
      code: 'N-1',
      name: 'Node',
      order: 1,
      energy_cost: 5,
      recommended_power: 100,
      coin_reward: 10,
      first_clear_gems: 5,
      first_clear_shards: 0,
      cleared: false,
      difficulty_tier: 'NORMAL',
      display_name: 'Node',
      requires_code: null,
      unlocked: true,
      power_floor: null,
      drop_meter: 0,
      drop_meter_cap: 0,
    }],
  }),
}))

vi.mock('../hooks/useGuild', () => ({
  useGuild: () => ({
    data: {
      my_role: 'OFFICER',
      guild: { id: 3, tag: 'RDX', name: 'Raiders', description: '', member_count: 12, members: [] },
    },
  }),
}))

vi.mock('../hooks/useRaid', () => ({
  useRaid: () => ({
    data: {
      id: 7,
      guild_id: 3,
      boss_name: 'The Consultant',
      boss_level: 35,
      max_hp: 100000,
      remaining_hp: 42000,
      state: 'ACTIVE',
      tier: 'T2',
      starts_at: '2026-05-21T12:00:00Z',
      ends_at: '2026-05-22T12:00:00Z',
      contributors: [],
    },
  }),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: unknown[] }) => {
    if (String(queryKey[0]) === 'battle-pass') return { data: null }
    return { data: [] }
  },
}))

vi.mock('../store/sound', () => ({
  useSoundStore: (selector: (state: { playBgm: (name: string) => void }) => unknown) =>
    selector({ playBgm: () => undefined }),
}))

describe('LobbyRoute', () => {
  it('surfaces live guild and raid state instead of placeholder guild copy', () => {
    render(<LobbyRoute />)

    expect(screen.getByText(/\[RDX\]/i)).toBeInTheDocument()
    expect(screen.getByText(/12 members/i)).toBeInTheDocument()
    expect(screen.getByText(/raid active/i)).toBeInTheDocument()
    expect(screen.getByText(/consultant/i)).toBeInTheDocument()
  })
})
