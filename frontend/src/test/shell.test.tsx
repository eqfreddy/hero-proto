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
  it('renders nav tabs when logged in', () => {
    useAuthStore.setState({ jwt: 'tok' })
    render(<Shell />, { wrapper })
    // NavBar renders tabs in both desktop strip and mobile drawer — use getAllByText
    expect(screen.getAllByText('Roster').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Stages').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Shop').length).toBeGreaterThan(0)
  })

  it('hides currency bar when not logged in', () => {
    render(<Shell />, { wrapper })
    expect(screen.queryByTestId('currency-bar')).not.toBeInTheDocument()
  })

  it('shows currency bar when logged in', () => {
    useAuthStore.setState({ jwt: 'tok' })
    render(<Shell />, { wrapper })
    expect(screen.getByTestId('currency-bar')).toBeInTheDocument()
  })
})
