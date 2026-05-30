import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import type { Hero } from '../types'
import { useMe } from '../hooks/useMe'
import { pullStandard, type SummonPullOutcome } from '../api/summon'
import { toast } from '../store/ui'
import './Lobby.css'
import './SummonV2Results.css'
import { assetUrl } from '../api/client'

const RARITY_ORDER = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']
const RARITY_LETTER: Record<string, string> = {
  COMMON: 'C',
  UNCOMMON: 'U',
  RARE: 'R',
  EPIC: 'E',
  LEGENDARY: 'L',
  MYTH: 'M',
}
const RARITY_TIER: Record<string, string> = {
  COMMON: 'FLOPPY',
  UNCOMMON: 'HARD-DISK',
  RARE: 'SSD',
  EPIC: 'RAID-0',
  LEGENDARY: 'RAID-5',
  MYTH: 'BLACKSITE',
}

interface ResultsState {
  heroes?: Hero[]
  outcomes?: SummonPullOutcome[]
  pullCount?: number
}

function HeroResultArt({ hero, className }: { hero: Hero; className?: string }) {
  const [mode, setMode] = useState<'card' | 'bust' | 'hidden'>('card')

  if (mode === 'hidden') return null

  const src = mode === 'card'
    ? assetUrl(`/app/static/heroes/cards/${hero.template.code}.png`)
    : assetUrl(`/app/static/heroes/busts/${hero.template.code}.png`)

  return (
    <img
      className={className}
      src={src}
      alt={hero.template.name}
      onError={() => setMode((current) => (current === 'card' ? 'bust' : 'hidden'))}
    />
  )
}

function rarityWeight(rarity: string): number {
  return RARITY_ORDER.indexOf(rarity)
}

function impactHeadline(outcome: SummonPullOutcome): string {
  const { hero } = outcome
  if (outcome.is_duplicate && (outcome.shards_granted ?? 0) > 0) {
    return `No new body, but +${outcome.shards_granted} shards is still real account movement when the next ascend is waiting.`
  }
  switch (hero.template.rarity) {
    case 'MYTH':
      return 'This is the kind of pull that changes how the whole account feels.'
    case 'LEGENDARY':
      return 'Real account-moving pull. This is where a roster starts looking expensive.'
    case 'EPIC':
      return 'Strong enough to change a team slot right now instead of someday.'
    case 'RARE':
      return 'Not a jackpot, but still enough to tighten the ladder and clean up campaign nodes.'
    default:
      return 'Bank the shards, keep the pity moving, and line up the next spike.'
  }
}

function arenaAngle(outcome: SummonPullOutcome, rating: number | undefined): string {
  const { hero } = outcome
  const score = rating ?? 0
  if (outcome.is_duplicate && (outcome.shards_granted ?? 0) > 0) {
    return 'This one does not change the frontline today, but the shard bank makes the next power spike easier to justify.'
  }
  if (rarityWeight(hero.template.rarity) >= rarityWeight('LEGENDARY')) {
    return score >= 1600
      ? 'This is immediate arena tech. Test it on offense and make people answer it.'
      : 'This is your cleanest route to stealing arena wins you were not supposed to get yet.'
  }
  if (rarityWeight(hero.template.rarity) >= rarityWeight('EPIC')) {
    return 'Solid ladder glue. Good enough to fix weak comps or force a better speed line.'
  }
  return 'More pressure than payoff. Use the shards, let pity climb, and keep hunting for a real closer.'
}

function nextMove(outcome: SummonPullOutcome, highCount: number): { label: string; path: string; body: string } {
  const { hero } = outcome
  if (outcome.is_duplicate && (outcome.shards_granted ?? 0) > 0) {
    return {
      label: 'Check Ascend',
      path: '/app/roster',
      body: 'The right duplicate is upgrade fuel. Open the roster and see who just got closer to a real breakpoint.',
    }
  }
  if (rarityWeight(hero.template.rarity) >= rarityWeight('LEGENDARY')) {
    return {
      label: 'Tune Arena Team',
      path: '/app/arena',
      body: 'A hit like this should be tested where it can bully somebody immediately.',
    }
  }
  if (highCount > 0) {
    return {
      label: 'Open Roster',
      path: '/app/roster',
      body: 'There is enough quality here to re-check your top five and power lane.',
    }
  }
  return {
    label: 'Run It Back',
    path: '/app/summon',
    body: 'This pull kept the meter alive. Go again while the pity math is still warming up.',
  }
}

export function SummonV2ResultsRoute() {
  const location = useLocation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: me } = useMe()
  const state = location.state as ResultsState | null
  const heroes = state?.heroes ?? []
  const outcomes = useMemo(() => {
    if (state?.outcomes?.length) return state.outcomes
    return heroes.map((hero) => ({
      hero,
      rarity: hero.template.rarity,
      pulled_epic_pity: false,
      is_duplicate: false,
      shards_granted: 0,
    }))
  }, [heroes, state?.outcomes])
  const pullCount = state?.pullCount ?? heroes.length
  const faction = me?.faction ?? 'EXILE'
  const [repulling, setRepulling] = useState(false)

  const freeCredits = me?.free_summon_credits ?? 0
  const usingFreeRepull = pullCount === 1 && freeCredits > 0
  const repullCost = pullCount === 10 ? 10 : 1
  const canRepull = !repulling && (pullCount === 10 ? (me?.shards ?? 0) >= repullCost : usingFreeRepull || (me?.shards ?? 0) >= repullCost)

  async function repull() {
    if (!canRepull) return
    setRepulling(true)
    try {
      const count = (pullCount === 10 ? 10 : 1) as 1 | 10
      const res = await pullStandard(count)
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
      navigate('/app/summon/results', {
        replace: true,
        state: { heroes: res.heroes, outcomes: res.outcomes, pullCount: count },
      })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'pull failed')
      setRepulling(false)
    }
  }

  const headliner = useMemo(() => {
    if (!outcomes.length) return null
    return [...outcomes].sort((a, b) => rarityWeight(b.hero.template.rarity) - rarityWeight(a.hero.template.rarity))[0]
  }, [outcomes])

  const summary = useMemo(() => {
    const counts = { c: 0, u: 0, r: 0, e: 0, l: 0, m: 0, duplicates: 0, shards: 0 }
    for (const outcome of outcomes) {
      switch (outcome.hero.template.rarity) {
        case 'COMMON':
          counts.c++
          break
        case 'UNCOMMON':
          counts.u++
          break
        case 'RARE':
          counts.r++
          break
        case 'EPIC':
          counts.e++
          break
        case 'LEGENDARY':
          counts.l++
          break
        case 'MYTH':
          counts.m++
          break
      }
      if (outcome.is_duplicate) counts.duplicates++
      counts.shards += outcome.shards_granted ?? 0
    }
    const high = counts.e + counts.l + counts.m
    const mid = counts.r + counts.u
    return { high, mid, low: counts.c, duplicates: counts.duplicates, shards: counts.shards, total: heroes.length }
  }, [heroes.length, outcomes])

  if (!heroes.length || !headliner) {
    return (
      <div className="lobby-root" data-faction={faction}>
        <div className="res-hdr">
          <div className="eyebrow">// no recent pull</div>
          <div className="title">RESULTS</div>
        </div>
        <div className="res-empty">
          NO PULL DATA IN SESSION
          <br />
          <Link className="link" to="/app/summon">
            {'< BACK TO SUMMON'}
          </Link>
        </div>
      </div>
    )
  }

  const headlinerRarity = headliner.hero.template.rarity
  const headlinerIsBig = ['EPIC', 'LEGENDARY', 'MYTH'].includes(headlinerRarity)
  const titleAccentClass =
    headlinerRarity === 'EPIC' ? 'accent epic'
    : headlinerRarity === 'MYTH' ? 'accent'
    : headlinerRarity === 'LEGENDARY' ? 'accent legend'
    : headlinerRarity === 'RARE' ? 'accent mid'
    : 'accent'
  const followUp = nextMove(headliner, summary.high)

  return (
    <div className="lobby-root" data-faction={faction}>
      <div className="res-hdr">
        <div className="eyebrow">// {pullCount}x pull - complete</div>
        <div className="title">
          {headlinerRarity} <span className={titleAccentClass}>PULLED</span>
        </div>
      </div>

      <div className="res-hero" data-rar={headlinerRarity}>
        <div className="rays" />
        {headlinerIsBig && <div className="pulse" />}
        <div className="label">
          // {headlinerRarity} - {RARITY_TIER[headlinerRarity] ?? ''}
        </div>
        <div className="name">
          {headliner.hero.template.name}
          <span className="sub">
            {headliner.hero.template.faction} - {headliner.hero.stars}* - {headliner.hero.template.role}
          </span>
        </div>
        <div className="fig-slot">
          <HeroResultArt hero={headliner.hero} className="bust" />
        </div>
      </div>

      <section className="res-impact">
        <article className="res-impact-card">
          <span className="res-impact-kicker">Roster Impact</span>
          <strong>{headliner.hero.template.name}</strong>
          <p>{impactHeadline(headliner)}</p>
        </article>
        <article className="res-impact-card">
          <span className="res-impact-kicker">Arena Angle</span>
          <strong>{headlinerRarity} pressure</strong>
          <p>{arenaAngle(headliner, me?.arena_rating)}</p>
        </article>
        <article className="res-impact-card">
          <span className="res-impact-kicker">Next Move</span>
          <strong>{followUp.label}</strong>
          <p>{followUp.body}</p>
        </article>
      </section>

      <div className="res-grid">
        {outcomes.map((outcome, index) => (
          <div key={`${outcome.hero.id}-${index}`} className="mini" data-rar={outcome.hero.template.rarity}>
            <span className="rar-mark">{RARITY_LETTER[outcome.hero.template.rarity] ?? '?'}</span>
            <div className="silhouette-mini">
              <HeroResultArt hero={outcome.hero} className="bust" />
            </div>
            <div className="nm">{outcome.hero.template.name}</div>
            {outcome.is_duplicate && (outcome.shards_granted ?? 0) > 0 && (
              <div className="dupe-tag">+{outcome.shards_granted} shards</div>
            )}
          </div>
        ))}
      </div>

      <div className="res-summary">
        <span>HIGH - <b className="new">{summary.high}</b></span>
        <span>MID - <b>{summary.mid}</b></span>
        <span>LOW - <b>{summary.low}</b></span>
        <span>DUPS - <b>{summary.duplicates}</b></span>
        <span>SHARDS - <b className="new">+{summary.shards}</b></span>
      </div>

      <div className="res-cta">
        <button type="button" onClick={() => navigate(followUp.path)}>
          {followUp.label}
        </button>
        <button type="button" className="primary" disabled={!canRepull} onClick={repull}>
          {repulling
            ? '...'
            : pullCount === 10
              ? `SUMMON x10 (${repullCost} SHARDS)`
              : usingFreeRepull
                ? 'FREE REPULL x1'
                : `AGAIN (${repullCost} SHARDS)`}
        </button>
      </div>
    </div>
  )
}

export default SummonV2ResultsRoute
