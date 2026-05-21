import { beforeEach, describe, expect, it, vi } from 'vitest'
import { postRaidInteractiveAct, postRaidInteractiveStart } from './raids'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('postRaidInteractiveStart', () => {
  it('posts the raid team to the raid interactive start endpoint', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'raid-abc', pending: null, team_a: [], team_b: [] }),
    })

    await postRaidInteractiveStart(12, [1, 2, 3])

    expect(mockFetch).toHaveBeenCalledWith(
      '/raids/12/attack/interactive/start',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ team: [1, 2, 3] }),
      }),
    )
  })
})

describe('postRaidInteractiveAct', () => {
  it('posts target, action, and turn to the raid interactive act endpoint', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'raid-abc', pending: null, team_a: [], team_b: [] }),
    })

    await postRaidInteractiveAct('raid-abc', 'B0', { actionType: 'skill', turnNumber: 4 })

    expect(mockFetch).toHaveBeenCalledWith(
      '/raids/interactive/raid-abc/act',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_uid: 'B0', action_type: 'skill', turn_number: 4 }),
      }),
    )
  })
})
