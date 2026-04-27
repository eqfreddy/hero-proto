import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiFetch } from '../api/client'
import { useAuthStore } from '../store/auth'

beforeEach(() => {
  localStorage.clear()
  useAuthStore.setState({ jwt: null })
  vi.restoreAllMocks()
})

describe('apiFetch', () => {
  it('sends Authorization header when JWT present', async () => {
    useAuthStore.setState({ jwt: 'test-token' })
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    )
    vi.stubGlobal('fetch', mockFetch)

    await apiFetch('/me')

    expect(mockFetch).toHaveBeenCalledWith(
      '/me',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
  })

  it('omits Authorization header when no JWT', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    )
    vi.stubGlobal('fetch', mockFetch)

    await apiFetch('/me')

    const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>
    expect(headers['Authorization']).toBeUndefined()
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    ))
    await expect(apiFetch('/me')).rejects.toThrow('Not found')
  })
})
