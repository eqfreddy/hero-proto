import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postBattle, postInteractiveStart, postAct } from './battles'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('postBattle', () => {
  it('posts correct payload to /battles', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: 42, account_id: 1, log: [] }),
    })
    const result = await postBattle({ stage_id: 3, team: [1, 2, 3], target_priority: 'lowest_hp' })
    expect(mockFetch).toHaveBeenCalledWith(
      '/battles',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ stage_id: 3, team: [1, 2, 3], target_priority: 'lowest_hp' }),
      }),
    )
    expect(result.id).toBe(42)
  })
})

describe('postInteractiveStart', () => {
  it('posts to /battles/interactive/start', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'abc', pending: null, team_a: [], team_b: [] }),
    })
    const result = await postInteractiveStart({ stage_id: 3, team: [1, 2] })
    expect(mockFetch).toHaveBeenCalledWith('/battles/interactive/start', expect.any(Object))
    expect(result.session_id).toBe('abc')
  })
})

describe('postAct', () => {
  it('posts target_uid to /battles/interactive/:sessionId/act', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'abc', pending: null, team_a: [], team_b: [] }),
    })
    await postAct('abc', 'unit-uid-1')
    expect(mockFetch).toHaveBeenCalledWith(
      '/battles/interactive/abc/act',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ target_uid: 'unit-uid-1' }) }),
    )
  })
})
