import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { RecycleBinFinisher } from './RecycleBinFinisher'

describe('RecycleBinFinisher', () => {
  it('renders the target name and a bin drop zone', () => {
    render(
      <RecycleBinFinisher
        targetUid="B0" targetName="glitchwraith"
        windowMs={2500} onResolve={() => {}}
      />,
    )
    expect(screen.getByText(/glitchwraith/i)).toBeTruthy()
    expect(screen.getByTestId('recycle-bin')).toBeTruthy()
    expect(screen.getByTestId('finisher-draggable')).toBeTruthy()
  })

  it('auto-resolves (plain) when the window elapses', () => {
    vi.useFakeTimers()
    const onResolve = vi.fn()
    render(
      <RecycleBinFinisher
        targetUid="B0" targetName="glitchwraith"
        windowMs={2500} onResolve={onResolve}
      />,
    )
    act(() => { vi.advanceTimersByTime(2600) })
    expect(onResolve).toHaveBeenCalledWith({ targetUid: 'B0', perfect: false })
    vi.useRealTimers()
  })

  it('resolves perfect via the accessible button', () => {
    const onResolve = vi.fn()
    render(
      <RecycleBinFinisher
        targetUid="B0" targetName="glitchwraith"
        windowMs={2500} onResolve={onResolve}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /delete now/i }))
    expect(onResolve).toHaveBeenCalledWith({ targetUid: 'B0', perfect: true })
  })
})
