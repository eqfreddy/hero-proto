import { fireEvent, render, screen } from '@testing-library/react'
import { GuildMembers } from './Members'

vi.mock('../../hooks/useGuild', () => ({
  useGuild: vi.fn(),
}))

vi.mock('../../store/ui', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../components/EmptyState', () => ({
  EmptyState: ({ message }: { message: string }) => <div>{message}</div>,
}))

const mockInvalidateQueries = vi.fn()
const mockSearchUsers = vi.fn()

vi.mock('../../api/friends', () => ({
  searchUsers: (...args: unknown[]) => mockSearchUsers(...args),
}))

vi.mock('../../api/guild', () => ({
  invitePlayer: vi.fn(),
  promoteMember: vi.fn(),
  demoteMember: vi.fn(),
  transferLeadership: vi.fn(),
  kickMember: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}))

describe('GuildMembers', () => {
  it('gives leaders member controls and invite search', async () => {
    const { useGuild } = await import('../../hooks/useGuild')
    vi.mocked(useGuild).mockReturnValue({
      data: {
        my_role: 'LEADER',
        guild: {
          id: 4,
          name: 'Night Ops',
          tag: 'NITE',
          description: '',
          member_count: 3,
          members: [
            { account_id: 1, name: 'leader', role: 'LEADER', arena_rating: 1800 },
            { account_id: 2, name: 'officer', role: 'OFFICER', arena_rating: 1600 },
            { account_id: 3, name: 'rookie', role: 'MEMBER', arena_rating: 1200 },
          ],
        },
      },
    } as never)
    mockSearchUsers.mockResolvedValue([{ id: 9, name: 'lurker', arena_rating: 1100, status: 'NONE' }])

    render(<GuildMembers />)

    expect(screen.getByText(/invite player/i)).toBeInTheDocument()
    expect(screen.getByText(/promote/i)).toBeInTheDocument()
    expect(screen.getByText(/demote/i)).toBeInTheDocument()
    expect(screen.getAllByText(/transfer lead/i).length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText(/search players/i), { target: { value: 'lurk' } })
    fireEvent.click(screen.getByText(/^search$/i))

    expect(await screen.findByText('lurker')).toBeInTheDocument()
    expect(screen.getAllByText(/invite/i).length).toBeGreaterThan(0)
  })

  it('keeps member view clean when you are not management', async () => {
    const { useGuild } = await import('../../hooks/useGuild')
    vi.mocked(useGuild).mockReturnValue({
      data: {
        my_role: 'MEMBER',
        guild: {
          id: 4,
          name: 'Night Ops',
          tag: 'NITE',
          description: '',
          member_count: 2,
          members: [
            { account_id: 1, name: 'leader', role: 'LEADER', arena_rating: 1800 },
            { account_id: 2, name: 'you', role: 'MEMBER', arena_rating: 1200 },
          ],
        },
      },
    } as never)

    render(<GuildMembers />)

    expect(screen.queryByText(/invite player/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/promote/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/kick/i)).not.toBeInTheDocument()
  })
})
