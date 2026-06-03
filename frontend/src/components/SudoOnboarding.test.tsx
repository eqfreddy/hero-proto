import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SudoOnboarding } from './SudoOnboarding'

const h = vi.hoisted(() => ({ level: 1 as number | undefined }))
vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ data: { account_level: h.level } }),
}))

describe('SudoOnboarding', () => {
  beforeEach(() => {
    localStorage.clear()
    h.level = 1
  })

  it('shows step 1 for a fresh level-1 account', () => {
    render(<SudoOnboarding />)
    expect(screen.getByText('Step 1 — Recruit')).toBeInTheDocument()
  })

  it('renders nothing for a higher-level account', () => {
    h.level = 5
    const { container } = render(<SudoOnboarding />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing once seen', () => {
    localStorage.setItem('heroproto_onboarding_seen', '1')
    const { container } = render(<SudoOnboarding />)
    expect(container).toBeEmptyDOMElement()
  })

  it('Next walks all three steps then dismisses + persists', () => {
    const { container } = render(<SudoOnboarding />)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2 — Build')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 3 — Deploy')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /got it/i }))
    expect(container).toBeEmptyDOMElement()
    expect(localStorage.getItem('heroproto_onboarding_seen')).toBe('1')
  })

  it('Skip dismisses immediately + persists', () => {
    const { container } = render(<SudoOnboarding />)
    fireEvent.click(screen.getByRole('button', { name: /skip tour/i }))
    expect(container).toBeEmptyDOMElement()
    expect(localStorage.getItem('heroproto_onboarding_seen')).toBe('1')
  })

  it('does not crash when the spotlight target is absent', () => {
    render(<SudoOnboarding />)
    expect(screen.getByText('Step 1 — Recruit')).toBeInTheDocument()
    expect(screen.queryByTestId('sudo-onb-ring')).toBeNull()
  })
})
