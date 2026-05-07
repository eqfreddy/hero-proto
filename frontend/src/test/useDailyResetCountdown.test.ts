import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useDailyResetCountdown } from '../hooks/useDailyResetCountdown'

describe('useDailyResetCountdown', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('returns time until next 00:00 UTC at noon UTC', () => {
    vi.setSystemTime(new Date('2026-05-06T12:00:00Z'))
    const { result } = renderHook(() => useDailyResetCountdown())
    expect(result.current).toBe('12:00:00')  // 12 hours
  })

  it('returns under-1h format when close to midnight', () => {
    vi.setSystemTime(new Date('2026-05-06T23:30:00Z'))
    const { result } = renderHook(() => useDailyResetCountdown())
    expect(result.current).toBe('30:00')  // 30 minutes
  })

  it('returns ~24h just after midnight UTC', () => {
    vi.setSystemTime(new Date('2026-05-06T00:00:30Z'))
    const { result } = renderHook(() => useDailyResetCountdown())
    expect(result.current).toBe('23:59:30')
  })
})
