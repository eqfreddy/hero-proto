import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { PlayNav } from './PlayNav'

// Toggle the active-event API response per test. vi.hoisted so the mock
// factory (hoisted above imports) can reference it safely.
const h = vi.hoisted(() => ({ event: null as unknown }))

vi.mock('../../api/events', () => ({
  fetchActiveEvent: () => Promise.resolve(h.event),
}))
vi.mock('../../hooks/useHeroes', () => ({
  useHeroes: () => ({ data: [] }),
}))

function renderNav() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/app/me']}>
        <PlayNav />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PlayNav', () => {
  beforeEach(() => {
    h.event = null
  })

  it('renders the five base hubs', () => {
    renderNav()
    for (const label of ['Home', 'Heroes', 'Battle', 'Shop', 'Social']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('hides the Event tab when no event is active', async () => {
    h.event = null
    renderNav()
    await screen.findByText('Home') // let the active-event query settle
    expect(screen.queryByText('Event')).toBeNull()
  })

  it('shows the Event tab when an event is active', async () => {
    h.event = { id: 'summer', display_name: 'Summer Outage' }
    renderNav()
    expect(await screen.findByText('Event')).toBeInTheDocument()
  })
})
