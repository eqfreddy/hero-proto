import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shell } from '../components/Layout/Shell'
import { useAuthStore } from '../store/auth'

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>
      {children}
    </MemoryRouter>
  </QueryClientProvider>
)

beforeEach(() => {
  useAuthStore.setState({ jwt: null })
  // Pre-confirm age gate so it doesn't intercept render in tests.
  localStorage.setItem('age_gate_v1', JSON.stringify({ confirmedAt: '2026-04-29T00:00:00Z', birthYear: 1990 }))
})

describe('Shell', () => {
  it('renders play nav tabs when logged in', () => {
    useAuthStore.setState({ jwt: 'tok' })
    render(<Shell />, { wrapper })
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByText('Heroes')).toBeInTheDocument()
    expect(screen.getByText('Battle')).toBeInTheDocument()
    expect(screen.getByText('Shop')).toBeInTheDocument()
  })

  it('does not render shared chrome when not logged in', () => {
    render(<Shell />, { wrapper })
    expect(screen.queryByText('Home')).not.toBeInTheDocument()
  })

  it('shows topnav chrome when logged in', () => {
    useAuthStore.setState({ jwt: 'tok' })
    render(<Shell />, { wrapper })
    expect(screen.getByText('[ HERO-PROTO ]')).toBeInTheDocument()
  })
})
