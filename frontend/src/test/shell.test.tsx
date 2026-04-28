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

beforeEach(() => useAuthStore.setState({ jwt: null }))

describe('Shell', () => {
  it('renders nav tabs', () => {
    render(<Shell />, { wrapper })
    expect(screen.getByText('Roster')).toBeInTheDocument()
    expect(screen.getByText('Stages')).toBeInTheDocument()
    expect(screen.getByText('Shop')).toBeInTheDocument()
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
