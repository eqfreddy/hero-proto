import { render, screen } from '@testing-library/react'
import { RaidsTabRoute } from './RaidsTab'

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
      contributors: [
        { account_id: 1, name: 'Alice', damage_dealt: 32000 },
        { account_id: 2, name: 'Bob', damage_dealt: 18000 },
      ],
    },
    isLoading: false,
  }),
}))

vi.mock('../hooks/useGuild', () => ({
  useGuild: () => ({ data: { guild: { id: 3, name: 'Raiders' } } }),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({
    data: [{ account_id: 9, name: 'Veteran', total_damage: 99000 }],
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

describe('RaidsTabRoute', () => {
  it('shows raid state, schedule, and current contributors', () => {
    render(<RaidsTabRoute />)

    expect(screen.getByText(/lvl 35/i)).toBeInTheDocument()
    expect(screen.getByText(/tier t2/i)).toBeInTheDocument()
    expect(screen.getByText(/active/i)).toBeInTheDocument()
    expect(screen.getByText(/2 raiders committed/i)).toBeInTheDocument()
    expect(screen.getAllByText('Alice').length).toBeGreaterThan(0)
    expect(screen.getByText(/ends/i)).toBeInTheDocument()
  })
})
