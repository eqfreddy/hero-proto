import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AgeGate } from '../components/AgeGate'

const wrap = (children: React.ReactNode, path = '/app/me') => (
  <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
)

beforeEach(() => {
  localStorage.clear()
})

describe('AgeGate', () => {
  it('renders the gate when no confirmation is stored', () => {
    render(wrap(<AgeGate><div>protected</div></AgeGate>))
    expect(screen.getByText(/age check/i)).toBeInTheDocument()
    expect(screen.queryByText('protected')).not.toBeInTheDocument()
  })

  it('renders children when confirmation is stored', () => {
    localStorage.setItem('age_gate_v1', JSON.stringify({ confirmedAt: '2026-04-29T00:00:00Z', birthYear: 1990 }))
    render(wrap(<AgeGate><div>protected</div></AgeGate>))
    expect(screen.getByText('protected')).toBeInTheDocument()
  })

  it('blocks under-13 birth years', () => {
    render(wrap(<AgeGate><div>protected</div></AgeGate>))
    const currentYear = new Date().getFullYear()
    fireEvent.change(screen.getByLabelText(/year were you born/i), {
      target: { value: String(currentYear - 5) },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    expect(screen.getByText(/can't play yet/i)).toBeInTheDocument()
    expect(screen.queryByText('protected')).not.toBeInTheDocument()
    expect(localStorage.getItem('age_gate_v1')).toBeNull()
  })

  it('confirms 13+ and persists, revealing children', () => {
    render(wrap(<AgeGate><div>protected</div></AgeGate>))
    const currentYear = new Date().getFullYear()
    fireEvent.change(screen.getByLabelText(/year were you born/i), {
      target: { value: String(currentYear - 25) },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    expect(screen.getByText('protected')).toBeInTheDocument()
    expect(localStorage.getItem('age_gate_v1')).not.toBeNull()
  })

  it('lets users read the privacy page even before confirming', () => {
    render(wrap(<AgeGate><div>protected</div></AgeGate>, '/app/privacy'))
    expect(screen.getByText('protected')).toBeInTheDocument()
    expect(screen.queryByText(/age check/i)).not.toBeInTheDocument()
  })

  it('rejects invalid year input', () => {
    render(wrap(<AgeGate><div>protected</div></AgeGate>))
    fireEvent.change(screen.getByLabelText(/year were you born/i), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    expect(screen.getByText(/valid 4-digit year/i)).toBeInTheDocument()
    expect(screen.queryByText('protected')).not.toBeInTheDocument()
  })
})
