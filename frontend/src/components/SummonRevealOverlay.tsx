import { useEffect, useMemo, useState } from 'react'
import type { Hero } from '../types'
import { assetUrl } from '../api/client'
import type { SummonPullOutcome } from '../api/summon'
import './SummonRevealOverlay.css'

const RARITY_ORDER = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']

type RevealPhase = 'signal' | 'lock' | 'classify' | 'reveal' | 'ready'

type RevealConfig = {
  accentClass: string
  timings: number[]
  classification: string
  warning: string
}

const REVEAL_CONFIG: Record<string, RevealConfig> = {
  COMMON: {
    accentClass: 'common',
    timings: [280, 520, 780, 1040],
    classification: 'Routine recruit signal',
    warning: 'Low threat. Fast-track to intake.',
  },
  UNCOMMON: {
    accentClass: 'uncommon',
    timings: [320, 620, 930, 1220],
    classification: 'Promising field operative',
    warning: 'Minor command interest. Keep the dossier moving.',
  },
  RARE: {
    accentClass: 'rare',
    timings: [380, 760, 1120, 1480],
    classification: 'Priority roster contact',
    warning: 'Stable combat upside detected.',
  },
  EPIC: {
    accentClass: 'epic',
    timings: [500, 980, 1460, 2120],
    classification: 'High-value command asset',
    warning: 'Bridge traffic elevated. Flag for immediate review.',
  },
  LEGENDARY: {
    accentClass: 'legendary',
    timings: [620, 1180, 1780, 2500],
    classification: 'Command-grade operative',
    warning: 'Sector-wide alert. Hold transmission until identity lock is clean.',
  },
  MYTH: {
    accentClass: 'myth',
    timings: [720, 1360, 2040, 2920],
    classification: 'Blacksite-level acquisition',
    warning: 'Clear the bridge. This signal is not routine.',
  },
}

const PHASES: RevealPhase[] = ['signal', 'lock', 'classify', 'reveal', 'ready']

function rarityWeight(rarity: string): number {
  return RARITY_ORDER.indexOf(rarity)
}

function rarityLetter(rarity: string): string {
  return rarity[0] ?? '?'
}

function phaseCopy(phase: RevealPhase, outcome: SummonPullOutcome, pullCount: number, config: RevealConfig) {
  const { hero } = outcome
  const shardLine = outcome.is_duplicate && (outcome.shards_granted ?? 0) > 0
    ? ` Duplicate converted into +${outcome.shards_granted} template shards.`
    : ''
  switch (phase) {
    case 'signal':
      return {
        eyebrow: pullCount === 10 ? 'Multi-signal sweep' : 'Incoming recruit signal',
        title: 'Bridge intercept engaged',
        body: pullCount === 10
          ? `Ten signatures hit the table. Command is isolating the strongest contact now.`
          : 'Holotable traffic is spiking. Keep the bridge quiet while command locks the source.',
      }
    case 'lock':
      return {
        eyebrow: 'Identity lock',
        title: 'Dossier hash resolving',
        body: `Cross-checking ${hero.template.faction} records and combat role markers before command approves the file.`,
      }
    case 'classify':
      return {
        eyebrow: 'Threat classification',
        title: config.classification,
        body: config.warning,
      }
    case 'reveal':
      return {
        eyebrow: 'Operative cleared',
        title: hero.template.name,
        body: `Deployment tag: ${hero.template.role}. ${hero.stars} star contact ready for field placement.${shardLine}`,
      }
    case 'ready':
      return {
        eyebrow: 'Command recommendation',
        title: hero.template.name,
        body: pullCount === 10
          ? 'Headliner identified. Review the full squad intake and decide who gets the first resource hit.'
          : outcome.is_duplicate && (outcome.shards_granted ?? 0) > 0
            ? `Signal is stable. Command banked +${outcome.shards_granted} shards, so this miss still moved the account.`
            : 'Signal is stable. Continue to the dossier and decide whether this belongs in arena, campaign, or the next pull.',
      }
  }
}

function RevealArt({ hero }: { hero: Hero }) {
  const [mode, setMode] = useState<'card' | 'bust' | 'silhouette'>('card')

  if (mode === 'silhouette') {
    return <div className="sum-reveal-silhouette" aria-hidden="true" />
  }

  const src = mode === 'card'
    ? assetUrl(`/app/static/heroes/cards/${hero.template.code}.png`)
    : assetUrl(`/app/static/heroes/busts/${hero.template.code}.png`)

  return (
    <img
      className={`sum-reveal-art ${mode}`}
      src={src}
      alt={hero.template.name}
      onError={() => setMode((current) => (current === 'card' ? 'bust' : 'silhouette'))}
    />
  )
}

export function SummonRevealOverlay({
  outcomes,
  pullCount,
  onContinue,
}: {
  outcomes: SummonPullOutcome[]
  pullCount: 1 | 10
  onContinue: () => void
}) {
  const headliner = useMemo(() => {
    return [...outcomes].sort((a, b) => rarityWeight(b.hero.template.rarity) - rarityWeight(a.hero.template.rarity))[0] ?? null
  }, [outcomes])
  const rankedOutcomes = useMemo(() => {
    return [...outcomes].sort((a, b) => rarityWeight(b.hero.template.rarity) - rarityWeight(a.hero.template.rarity))
  }, [outcomes])
  const intakeBoard = rankedOutcomes.slice(0, 4)
  const summary = useMemo(() => {
    return outcomes.reduce(
      (acc, hero) => {
        const weight = rarityWeight(hero.hero.template.rarity)
        if (weight >= rarityWeight('EPIC')) acc.high += 1
        else if (weight >= rarityWeight('RARE')) acc.mid += 1
        else acc.low += 1
        if (hero.is_duplicate) acc.duplicates += 1
        acc.shards += hero.shards_granted ?? 0
        return acc
      },
      { high: 0, mid: 0, low: 0, duplicates: 0, shards: 0 },
    )
  }, [outcomes])
  const [phaseIndex, setPhaseIndex] = useState(0)

  const rarity = headliner?.hero.template.rarity ?? 'COMMON'
  const config = REVEAL_CONFIG[rarity] ?? REVEAL_CONFIG.COMMON
  const phase = PHASES[phaseIndex] ?? 'ready'
  const copy = headliner ? phaseCopy(phase, headliner, pullCount, config) : null

  useEffect(() => {
    setPhaseIndex(0)
    if (!headliner) return
    const timers = config.timings.map((delay, index) =>
      window.setTimeout(() => setPhaseIndex(index + 1), delay),
    )
    return () => {
      for (const timer of timers) window.clearTimeout(timer)
    }
  }, [config, headliner, pullCount])

  if (!headliner || !copy) return null

  return (
    <div className={`sum-reveal ${config.accentClass}`} role="dialog" aria-modal="true">
      <div className="sum-reveal-scan" />
      <div className="sum-reveal-frame">
        <div className="sum-reveal-copy">
          <span className="sum-reveal-eyebrow">{copy.eyebrow}</span>
          <h2>{copy.title}</h2>
          <p>{copy.body}</p>
          {pullCount === 10 && (
            <div className="sum-reveal-intake">
              <div className="sum-reveal-intake-head">
                <span>Intake Board</span>
                <strong>{outcomes.length} contacts</strong>
              </div>
              <div className="sum-reveal-intake-grid">
                {intakeBoard.map((outcome) => (
                  <div key={outcome.hero.id} className="sum-reveal-intake-row">
                    <span className={`rarity rarity-${outcome.hero.template.rarity.toLowerCase()}`}>{rarityLetter(outcome.hero.template.rarity)}</span>
                    <strong>{outcome.hero.template.name}</strong>
                    {outcome.is_duplicate && <em>+{outcome.shards_granted ?? 0} shards</em>}
                  </div>
                ))}
              </div>
              <div className="sum-reveal-intake-summary">
                <span>High {summary.high}</span>
                <span>Mid {summary.mid}</span>
                <span>Low {summary.low}</span>
                <span>Dups {summary.duplicates}</span>
              </div>
            </div>
          )}
          <div className="sum-reveal-status">
            <span className={phaseIndex >= 1 ? 'on' : ''}>Signal</span>
            <span className={phaseIndex >= 2 ? 'on' : ''}>Lock</span>
            <span className={phaseIndex >= 3 ? 'on' : ''}>Classify</span>
            <span className={phaseIndex >= 4 ? 'on' : ''}>Deploy</span>
          </div>
          {phase === 'ready' && (
            <button type="button" className="sum-reveal-cta" onClick={onContinue}>
              Continue To Dossier
            </button>
          )}
        </div>
        <div className={`sum-reveal-visual phase-${phase}`}>
          <div className="sum-reveal-grid" />
          <RevealArt hero={headliner.hero} />
          <div className="sum-reveal-label">
            <span>{headliner.hero.template.rarity}</span>
            <strong>{headliner.hero.template.name}</strong>
            {headliner.is_duplicate && (headliner.shards_granted ?? 0) > 0 && (
              <em>duplicate {'->'} +{headliner.shards_granted} shards</em>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SummonRevealOverlay
