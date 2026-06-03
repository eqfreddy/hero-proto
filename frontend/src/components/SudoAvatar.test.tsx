import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SudoAvatar } from './SudoAvatar'

describe('SudoAvatar', () => {
  it('renders the SUDO daemon face', () => {
    render(<SudoAvatar />)
    const el = screen.getByTestId('sudo-avatar')
    expect(el).toBeInTheDocument()
    expect(el.getAttribute('aria-label')).toBe('SUDO')
  })

  it('honors the size prop', () => {
    render(<SudoAvatar size={80} />)
    expect(screen.getByTestId('sudo-avatar').getAttribute('width')).toBe('80')
  })
})
