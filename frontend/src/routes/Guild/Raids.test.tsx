import { render, screen } from '@testing-library/react'
import { GuildRaids } from './Raids'

vi.mock('../../hooks/useGuild', () => ({
  useGuild: () => ({
    data: {
      guild: { id: 4, name: 'Night Ops' },
    },
  }),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({
    data: {
      id: 11,
      guild_id: 4,
      boss_name: 'The Consultant',
      boss_level: 28,
      max_hp: 80000,
      remaining_hp: 12000,
      state: 'ACTIVE',
      tier: 'T1',
      // Relative to now so the "clock is running" assertion never rots:
      // window opened an hour ago, closes six hours out.
      starts_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      ends_at: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
      contributors: [
        { account_id: 1, name: 'Alice', damage_dealt: 54000 },
        { account_id: 2, name: 'Bob', damage_dealt: 14000 },
      ],
    },
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

describe('GuildRaids', () => {
  it('shows contributor pressure and remaining time instead of only hp', () => {
    render(<GuildRaids />)

    expect(screen.getByText(/lvl 28/i)).toBeInTheDocument()
    expect(screen.getAllByText(/alice/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/54,000/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/clock is running/i)).toBeInTheDocument()
  })
})
