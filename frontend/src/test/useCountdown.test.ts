import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCountdown } from '../hooks/useCountdown'

describe('useCountdown', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('formats below 1 hour as M:SS', () => {
    const { result } = renderHook(() => useCountdown(222))  // 3:42
    expect(result.current).toBe('3:42')
  })

  it('formats above 1 hour as H:MM:SS', () => {
    const { result } = renderHook(() => useCountdown(8070))  // 2:14:30
    expect(result.current).toBe('2:14:30')
  })

  it('ticks down once per second', () => {
    const { result } = renderHook(() => useCountdown(10))
    expect(result.current).toBe('0:10')
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current).toBe('0:09')
    act(() => { vi.advanceTimersByTime(3000) })
    expect(result.current).toBe('0:06')
  })

  it('returns 0:00 at zero and stops', () => {
    const { result } = renderHook(() => useCountdown(2))
    act(() => { vi.advanceTimersByTime(5000) })
    expect(result.current).toBe('0:00')
  })

  it('resets when source seconds change', () => {
    const { result, rerender } = renderHook(
      ({ s }: { s: number }) => useCountdown(s),
      { initialProps: { s: 60 } },
    )
    expect(result.current).toBe('1:00')
    act(() => { vi.advanceTimersByTime(10_000) })
    expect(result.current).toBe('0:50')
    rerender({ s: 300 })
    expect(result.current).toBe('5:00')
  })

  it('returns 0:00 immediately for non-positive input', () => {
    const { result } = renderHook(() => useCountdown(0))
    expect(result.current).toBe('0:00')
  })

  it('calls onZero exactly once when crossing to 0', () => {
    const onZero = vi.fn()
    renderHook(() => useCountdown(2, onZero))
    act(() => { vi.advanceTimersByTime(2500) })
    expect(onZero).toHaveBeenCalledTimes(1)
  })
})
