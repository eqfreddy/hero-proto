import { useEffect, useMemo, useState } from 'react'
import type { Hero } from '../types'
import { assetUrl } from '../api/client'
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

function phaseCopy(phase: RevealPhase, hero: Hero, pullCount: number, config: RevealConfig) {
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
        body: `Deployment tag: ${hero.template.role}. ${hero.stars} star contact ready for field placement.`,
      }
    case 'ready':
      return {
        eyebrow: 'Command recommendation',
        title: hero.template.name,
        body: pullCount === 10
          ? 'Headliner identified. Review the full squad intake and decide who gets the first resource hit.'
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
  heroes,
  pullCount,
  onContinue,
}: {
  heroes: Hero[]
  pullCount: 1 | 10
  onContinue: () => void
}) {
  const headliner = useMemo(() => {
    return [...heroes].sort((a, b) => rarityWeight(b.template.rarity) - rarityWeight(a.template.rarity))[0] ?? null
  }, [heroes])
  const [phaseIndex, setPhaseIndex] = useState(0)

  const rarity = headliner?.template.rarity ?? 'COMMON'
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
          <RevealArt hero={headliner} />
          <div className="sum-reveal-label">
            <span>{headliner.template.rarity}</span>
            <strong>{headliner.template.name}</strong>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SummonRevealOverlay
