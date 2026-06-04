import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { EventRoute } from './Event'

// Mutable holder so each test can shape the active-event payload (banner /
// bundle present or absent) without re-hoisting the mock.
const h = vi.hoisted(() => ({
  data: null as Record<string, unknown> | null,
}))

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useQuery: () => ({ data: h.data, isLoading: false }),
}))

vi.mock('../store/ui', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const BASE = {
  id: 'ops-breach',
  display_name: 'Ops Breach',
  currency_name: 'Breach Chips',
  currency_emoji: 'CHIP',
  currency_balance: 145,
  ends_at: '2099-01-01T00:00:00Z',
  quests: [
    { code: 'clear-1', title: 'Clear 3 stages', goal: 3, progress: 3, currency_reward: 20, completed: true, claimed: false },
    { code: 'raid-1', title: 'Land a raid hit', goal: 1, progress: 1, currency_reward: 30, completed: true, claimed: true },
  ],
  milestones: [
    { idx: 1, title: 'Cache Bundle', cost: 100, contents: {}, redeemed: false, affordable: true },
    { idx: 2, title: 'Signal Pack', cost: 180, contents: {}, redeemed: false, affordable: false },
  ],
  banner: null as unknown,
  bundle: null as unknown,
}

function renderEvent() {
  return render(
    <MemoryRouter>
      <EventRoute />
    </MemoryRouter>,
  )
}

describe('EventRoute', () => {
  it('surfaces event pressure, quests, and milestone progress', () => {
    h.data = { ...BASE }
    renderEvent()

    expect(screen.getByText(/ops breach/i)).toBeInTheDocument()
    expect(screen.getByText(/1\/2/i)).toBeInTheDocument()
    expect(screen.getByText(/1 redeemable/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /redeem/i })).toBeInTheDocument()
    expect(screen.getByText(/need 35/i)).toBeInTheDocument()
    expect(screen.getByText(/145/i)).toBeInTheDocument()
  })

  it('hides the storefront cards when there is no banner or bundle', () => {
    h.data = { ...BASE, banner: null, bundle: null }
    renderEvent()
    expect(screen.queryByText(/featured banner/i)).toBeNull()
    expect(screen.queryByRole('link', { name: /summon/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /bundle/i })).toBeNull()
  })

  it('shows the featured banner card with a summon CTA', () => {
    h.data = {
      ...BASE,
      banner: { hero_template_code: 'applecrumb', hero_name: 'Applecrumb', shard_cost: 8, per_account_cap: 5, owned: 2 },
    }
    renderEvent()

    expect(screen.getByText(/applecrumb/i)).toBeInTheDocument()
    expect(screen.getByText(/2\/5/)).toBeInTheDocument() // owned / cap
    const cta = screen.getByRole('link', { name: /summon/i })
    expect(cta).toHaveAttribute('href', expect.stringContaining('/app/summon'))
  })

  it('shows the limited bundle card with price and a buy CTA', () => {
    h.data = {
      ...BASE,
      bundle: {
        sku: 'mothers_day_2026_bouquet',
        title: "Mother's Day Bouquet",
        description: 'Floral PowerPoint deck included.',
        price_cents: 1199,
        contents: { gems: 1200, shards: 150 },
        per_account_limit: 1,
        purchased: false,
      },
    }
    renderEvent()

    expect(screen.getByText(/mother's day bouquet/i)).toBeInTheDocument()
    expect(screen.getByText(/\$11\.99/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /bundle/i })).toBeInTheDocument()
  })

  it('hides the bundle card once purchased', () => {
    h.data = {
      ...BASE,
      bundle: {
        sku: 'mothers_day_2026_bouquet',
        title: "Mother's Day Bouquet",
        description: '',
        price_cents: 1199,
        contents: {},
        per_account_limit: 1,
        purchased: true,
      },
    }
    renderEvent()
    expect(screen.queryByText(/mother's day bouquet/i)).toBeNull()
  })
})
