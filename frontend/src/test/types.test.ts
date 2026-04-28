import type { Me, Hero, HeroTemplate, Stage, Guild, Notification } from '../types'

// TypeScript compile test — if the interfaces are missing or wrong, tsc fails.
const me: Me = {
  id: 1, email: 'a@b.com', coins: 0, gems: 0, shards: 0,
  access_cards: 0, free_summon_credits: 0, energy: 60, energy_cap: 60,
  pulls_since_epic: 0, stages_cleared: [], arena_rating: 1000,
  arena_wins: 0, arena_losses: 0, account_level: 1, account_xp: 0,
  qol_unlocks: {}, active_cosmetic_frame: '',
}

const tmpl: HeroTemplate = {
  id: 1, code: 'hr_001', name: 'Test', rarity: 'COMMON', role: 'ATK',
  faction: 'EXILE', attack_kind: 'melee', base_hp: 100, base_atk: 10,
  base_def: 10, base_spd: 10,
}

const hero: Hero = {
  id: 1, template: tmpl, level: 1, stars: 1, special_level: 1,
  power: 100, hp: 100, atk: 10, def_: 10, spd: 10,
  has_variance: false, variance_net: 0, dupe_count: 1, instance_ids: [1],
}

// Type guards to verify types exist (unused to satisfy noUnusedLocals is ok for types)
const stageGuard: (x: unknown) => x is Stage = (x): x is Stage => typeof x === 'object'
const guildGuard: (x: unknown) => x is Guild = (x): x is Guild => typeof x === 'object'
const notificationGuard: (x: unknown) => x is Notification = (x): x is Notification => typeof x === 'object'

describe('types compile', () => {
  it('Me shape', () => expect(me.email).toBe('a@b.com'))
  it('Hero shape', () => expect(hero.template.name).toBe('Test'))
  it('Stage type exists', () => expect(stageGuard).toBeDefined())
  it('Guild type exists', () => expect(guildGuard).toBeDefined())
  it('Notification type exists', () => expect(notificationGuard).toBeDefined())
})
