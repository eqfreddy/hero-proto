import { render, screen } from '@testing-library/react'
import { GuildOverview, GuildRoute } from './index'

const mockInvalidateQueries = vi.fn()

vi.mock('../../hooks/useGuild', () => ({
  useGuild: vi.fn(),
}))

vi.mock('../../components/SubNav', () => ({
  SubNav: () => <div>Guild Tabs</div>,
}))

vi.mock('../../components/SkeletonGrid', () => ({
  SkeletonGrid: () => <div>Loading…</div>,
}))

vi.mock('../../components/CoachMark', () => ({
  CoachMark: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../store/ui', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../api/guild', () => ({
  fetchAllGuilds: vi.fn(),
  createGuild: vi.fn(),
  applyToGuild: vi.fn(),
  leaveGuild: vi.fn(),
  fetchMyApplications: vi.fn(),
  withdrawApplication: vi.fn(),
  fetchMyInvites: vi.fn(),
  acceptInvite: vi.fn(),
  rejectInvite: vi.fn(),
  fetchGuildApplications: vi.fn(),
  acceptApplication: vi.fn(),
  rejectApplication: vi.fn(),
  fetchOutgoingInvites: vi.fn(),
  cancelInvite: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
  useQuery: ({ queryKey }: { queryKey: unknown[] }) => {
    const key = String(queryKey[0])
    if (key === 'guilds-all') {
      return { data: [{ id: 2, tag: 'OPS', name: 'Ops Crew', member_count: 9 }] }
    }
    if (key === 'guild-applications-mine') {
      return {
        data: [
          {
            id: 11,
            guild_id: 2,
            account_id: 8,
            applicant_name: 'player',
            status: 'PENDING',
            message: '',
            created_at: '2026-05-21T12:00:00Z',
            reviewed_at: null,
            reviewed_by: null,
          },
        ],
      }
    }
    if (key === 'guild-invites-mine') {
      return {
        data: [
          {
            id: 31,
            guild_id: 7,
            guild_name: 'Night Shift',
            guild_tag: 'NITE',
            account_id: 8,
            invitee_name: 'player',
            inviter_id: 5,
            inviter_name: 'lead',
            status: 'PENDING',
            message: 'come hit the raid boss',
            created_at: '2026-05-21T12:00:00Z',
            decided_at: null,
          },
        ],
      }
    }
    if (key === 'guild-applications') {
      return {
        data: [
          {
            id: 99,
            guild_id: 3,
            account_id: 14,
            applicant_name: 'newguy',
            status: 'PENDING',
            message: 'i do my dailies',
            created_at: '2026-05-21T12:00:00Z',
            reviewed_at: null,
            reviewed_by: null,
          },
        ],
      }
    }
    if (key === 'guild-invites-outgoing') {
      return {
        data: [
          {
            id: 77,
            guild_id: 3,
            guild_name: 'Raiders',
            guild_tag: 'RDX',
            account_id: 22,
            invitee_name: 'lurker',
            inviter_id: 1,
            inviter_name: 'lead',
            status: 'PENDING',
            message: 'join for weekly clears',
            created_at: '2026-05-21T12:00:00Z',
            decided_at: null,
          },
        ],
      }
    }
    return { data: [] }
  },
}))

describe('GuildRoute join funnel', () => {
  it('shows incoming invites and pending applications when the player has no guild', async () => {
    const { useGuild } = await import('../../hooks/useGuild')
    vi.mocked(useGuild).mockReturnValue({ data: { guild: null, my_role: null }, isLoading: false } as never)

    render(<GuildRoute />)

    expect(screen.getByText(/incoming invites/i)).toBeInTheDocument()
    expect(screen.getByText(/night shift/i)).toBeInTheDocument()
    expect(screen.getByText(/pending applications/i)).toBeInTheDocument()
    expect(screen.getAllByText(/ops crew/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/applied/i)).toBeInTheDocument()
  })
})

describe('GuildOverview officer inbox', () => {
  it('shows pending applicants and outgoing invites for officers', async () => {
    const { useGuild } = await import('../../hooks/useGuild')
    vi.mocked(useGuild).mockReturnValue({
      data: {
        my_role: 'OFFICER',
        guild: { id: 3, tag: 'RDX', name: 'Raiders', description: 'ship it', member_count: 12, members: [] },
      },
    } as never)

    render(<GuildOverview />)

    expect(screen.getByText(/officer inbox/i)).toBeInTheDocument()
    expect(screen.getByText(/newguy/i)).toBeInTheDocument()
    expect(screen.getByText(/outgoing invites/i)).toBeInTheDocument()
    expect(screen.getByText(/lurker/i)).toBeInTheDocument()
  })
})
