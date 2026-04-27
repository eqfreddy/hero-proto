import { render, screen } from '@testing-library/react'
import { HeroCard } from '../components/HeroCard'
import type { Hero } from '../types'

const hero: Hero = {
  id: 1,
  template: {
    id: 1, code: 'hr_jaded_intern', name: 'Jaded Intern',
    rarity: 'COMMON', role: 'ATK', faction: 'EXILE',
    attack_kind: 'melee', base_hp: 100, base_atk: 10, base_def: 10, base_spd: 10,
  },
  level: 5, stars: 2, special_level: 1,
  power: 450, hp: 200, atk: 30, def_: 20, spd: 15,
  has_variance: false, variance_net: 0, dupe_count: 1, instance_ids: [1],
}

describe('HeroCard', () => {
  it('shows hero name', () => {
    render(<HeroCard hero={hero} />)
    expect(screen.getByText('Jaded Intern')).toBeInTheDocument()
  })

  it('shows power', () => {
    render(<HeroCard hero={hero} />)
    expect(screen.getByText(/450/)).toBeInTheDocument()
  })

  it('shows rarity pill', () => {
    render(<HeroCard hero={hero} />)
    expect(screen.getByText('COMMON')).toBeInTheDocument()
  })

  it('shows dupe badge when count > 1', () => {
    render(<HeroCard hero={{ ...hero, dupe_count: 3 }} />)
    expect(screen.getByText('×3')).toBeInTheDocument()
  })
})
