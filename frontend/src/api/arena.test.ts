import { beforeEach, describe, expect, it, vi } from 'vitest'
import { attackArena, fetchArena } from './arena'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('fetchArena', () => {
  it('maps backend arena shapes into the client contract', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([
          { account_id: 7, name: 'rival', team_power: 1234, arena_rating: 1100 },
        ]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([
          { account_id: 9, email: 'ladder@example.com', arena_rating: 1400, arena_wins: 12, arena_losses: 3 },
        ]),
      })

    const result = await fetchArena()

    expect(result.opponents).toEqual([
      { account_id: 7, name: 'rival', defense_power: 1234, arena_rating: 1100 },
    ])
    expect(result.leaderboard).toEqual([
      { account_id: 9, name: 'ladder', arena_rating: 1400, wins: 12, losses: 3 },
    ])
    expect(result.recent).toEqual([])
  })
})

describe('attackArena', () => {
  it('posts defender_account_id and team to the backend', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: 55, outcome: 'WIN', rating_delta: 25, rewards: { coins: 10, shards: 1, gems: 0 } }),
    })

    await attackArena(88, [1, 2, 3])

    expect(mockFetch).toHaveBeenCalledWith(
      '/arena/attack',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ defender_account_id: 88, team: [1, 2, 3] }),
      }),
    )
  })
})
