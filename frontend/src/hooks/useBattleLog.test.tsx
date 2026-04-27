import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { useBattleLog } from './useBattleLog'

vi.mock('../api/battles', () => ({
  fetchBattle: vi.fn(async (id) => ({ id: Number(id), account_id: 1, log: [{ event: 'start' }] })),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useBattleLog', () => {
  it('fetches battle by id', async () => {
    const { result } = renderHook(() => useBattleLog('42'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.id).toBe(42)
    expect(result.current.data?.log).toHaveLength(1)
  })

  it('skips fetch when id is undefined', () => {
    const { result } = renderHook(() => useBattleLog(undefined), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
  })
})
