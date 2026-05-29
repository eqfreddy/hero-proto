import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { pullStandard, type SummonPullOutcome } from '../api/summon'
import { fetchFriendPoints, summonFriendBanner } from '../api/friendPoints'
import { toast } from '../store/ui'
import type { Hero } from '../types'
import './Lobby.css'
import './SummonV2.css'
import { assetUrl } from '../api/client'
import { SummonRevealOverlay } from '../components/SummonRevealOverlay'

const PITY_CAP = 50
const SOFT_PITY = 35
const COST_X1 = 1
const COST_X10 = 10

type BannerKind = 'STD' | 'FRIEND'

const RARITY_LETTER: Record<string, string> = {
  COMMON: 'C',
  UNCOMMON: 'U',
  RARE: 'R',
  EPIC: 'E',
  LEGENDARY: 'L',
  MYTH: 'M',
}

function arenaEdgeCopy(rating: number | undefined): string {
  const score = rating ?? 0
  if (score >= 1800) return 'Your bracket is already serious. One hit banner upgrades can turn a good defense into a miserable one.'
  if (score >= 1400) return 'You are close enough for one strong pull to swing the next bracket and force harder counters.'
  return 'Better pulls make the campaign easier and the ladder stop feeling uphill.'
}

function summaryTone(pity: number, softHit: boolean): 'heated' | 'base' {
  if (pity >= 45 || softHit) return 'heated'
  return 'base'
}

function rosterPressureCopy(heroes: Hero[] | undefined): { title: string; body: string } {
  if (!heroes?.length) {
    return {
      title: 'Fresh account pressure',
      body: 'You do not have enough bodies online yet, so every quality hit is still a direct roster unlock.',
    }
  }

  const premiumCount = heroes.filter((hero) => ['EPIC', 'LEGENDARY', 'MYTH'].includes(hero.template.rarity)).length
  const uniqueRoles = new Set(heroes.slice(0, 6).map((hero) => hero.template.role)).size
  const uniqueFactions = new Set(heroes.map((hero) => hero.template.faction)).size

  if (premiumCount === 0) {
    return {
      title: 'No closer online',
      body: 'You still do not own a real premium carry, so one banner hit can completely change both campaign pace and arena threat.',
    }
  }
  if (premiumCount === 1) {
    return {
      title: 'One premium carry only',
      body: 'The roster has a headliner, but not enough support around it yet. Another real hit makes the whole account less one-note.',
    }
  }
  if (uniqueRoles < 3) {
    return {
      title: 'Role coverage is thin',
      body: 'Your top crew is still missing one lane of pressure. Summons that widen role coverage make team-building stop feeling solved too early.',
    }
  }
  if (uniqueFactions < 2) {
    return {
      title: 'Faction pool is shallow',
      body: 'Right now the account leans too hard on one camp. More faction depth gives you cleaner pivots when a stage or arena meta gets annoying.',
    }
  }
  return {
    title: 'Roster still has room',
    body: 'The account is functional now, which means good pulls stop being survival and start being leverage. That is the dangerous spend zone.',
  }
}

function HeroPromoArt({ hero, className }: { hero: Hero | null; className?: string }) {
  const [mode, setMode] = useState<'card' | 'bust' | 'silhouette'>('card')

  if (!hero || mode === 'silhouette') {
    return <SilhouettePurple />
  }

  const src = mode === 'card'
    ? assetUrl(`/app/static/heroes/cards/${hero.template.code}.png`)
    : assetUrl(`/app/static/heroes/busts/${hero.template.code}.png`)

  return (
    <img
      className={className}
      src={src}
      alt={hero.template.name}
      onError={() => setMode((current) => (current === 'card' ? 'bust' : 'silhouette'))}
    />
  )
}

export function SummonV2Route() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: fp } = useQuery({
    queryKey: ['friend-points'],
    queryFn: fetchFriendPoints,
    refetchInterval: 60_000,
    retry: 1,
  })
  const [pulling, setPulling] = useState(false)
  const [lastPull, setLastPull] = useState<Hero[] | null>(null)
  const [banner, setBanner] = useState<BannerKind>('STD')
  const [revealState, setRevealState] = useState<{ heroes: Hero[]; outcomes: SummonPullOutcome[]; pullCount: 1 | 10 } | null>(null)

  const pity = me?.pulls_since_epic ?? 0
  const pityPct = Math.min(100, (pity / PITY_CAP) * 100)
  const pullsToEpic = Math.max(0, PITY_CAP - pity)
  const softHit = pity >= SOFT_PITY
  const shards = me?.shards ?? 0
  const freeCredits = me?.free_summon_credits ?? 0
  const usingFreePull = freeCredits > 0
  const canX1 = (usingFreePull || shards >= COST_X1) && !pulling
  const canX10 = shards >= COST_X10 && !pulling

  const fpBalance = fp?.balance ?? 0
  const fpCost = fp?.fp_per_summon ?? 100
  const fpPity = fp?.fp_pulls_since_epic ?? 0
  const fpCap = fp?.fp_pity_threshold ?? 50
  const fpPityPct = Math.min(100, (fpPity / fpCap) * 100)
  const canFriendPull = fpBalance >= fpCost && !pulling
  const pityState = pity >= 45 ? 'critical' : softHit ? 'heated' : pity >= 20 ? 'warming' : 'cold'
  const x1Tone = usingFreePull ? 'free' : pity >= 45 ? 'critical' : softHit ? 'heated' : 'base'
  const x10Tone = pity >= 45 ? 'sweep-critical' : summaryTone(pity, softHit)

  const featuredHero = useMemo(() => {
    if (!heroes?.length) return null
    const rare = heroes.find((h) => ['EPIC', 'LEGENDARY', 'MYTH'].includes(h.template.rarity))
    return rare ?? null
  }, [heroes])
  const rosterPressure = useMemo(() => rosterPressureCopy(heroes), [heroes])

  const standardPressureCards = [
    {
      title: usingFreePull ? `${freeCredits} free pull${freeCredits === 1 ? '' : 's'} is loaded` : 'Banner ready',
      body: usingFreePull
        ? `Burn the free ticket first. ${freeCredits > 1 ? `${freeCredits} total credits are stacked,` : 'The account already has a credit,'} so the next x1 costs zero shards.`
        : 'No free credit loaded, so the next x1 comes straight out of shards.',
    },
    {
      title: `${pity}/${PITY_CAP} pity`,
      body: softHit
        ? `Soft pity is already active. ${pullsToEpic} pulls from the hard stop means every click feels heavier now.`
        : `${pullsToEpic} pulls until the guaranteed epic floor. This is where the chase starts to feel mathematically real.`,
    },
    {
      title: 'Arena edge',
      body: arenaEdgeCopy(me?.arena_rating),
    },
    {
      title: rosterPressure.title,
      body: rosterPressure.body,
    },
    {
      title: pity >= 45 ? 'Now or never territory' : softHit ? 'Banner is heating up' : 'No free lunch',
      body: pity >= 45
        ? 'The next few pulls are the exact zone where spend and competitive itch start talking to each other.'
        : softHit
          ? 'The meter is hot enough that even one pull feels different now. This is where people start hovering.'
          : 'You are still early, so the smart pitch is free value, roster growth, and lining up the next pity spike.',
    },
  ]

  const faction = me?.faction ?? 'EXILE'

  async function pull(count: 1 | 10) {
    if (pulling) return
    setPulling(true)
    setLastPull(null)
    try {
      const res = await pullStandard(count)
      setLastPull(res.heroes)
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
      setRevealState({ heroes: res.heroes, outcomes: res.outcomes, pullCount: count })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'pull failed')
    } finally {
      setPulling(false)
    }
  }

  async function pullFriend() {
    if (pulling) return
    setPulling(true)
    setLastPull(null)
    try {
      const res = await summonFriendBanner()
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['heroes'] })
      qc.invalidateQueries({ queryKey: ['friend-points'] })
      if (res.hero) {
        setRevealState({ heroes: [res.hero], outcomes: [res], pullCount: 1 })
      } else {
        navigate('/app/summon/results', { state: { heroes: [], pullCount: 1 } })
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'friend pull failed')
    } finally {
      setPulling(false)
    }
  }

  return (
    <div className="lobby-root" data-faction={faction}>
      <div className="sum-hdr">
        <button type="button" className="back" onClick={() => navigate('/app/me')}>
          {'< COMMAND DECK'}
        </button>
        <span className="title">SUMMON.exe</span>
        <span className="right">
          <span className="pill">
            {banner === 'STD' ? `${shards.toLocaleString()} SHARDS` : `${fpBalance.toLocaleString()} FP`}
          </span>
        </span>
      </div>

      {fp && (
        <div className="sum-tabs">
          <button
            type="button"
            className={`tab${banner === 'STD' ? ' on' : ''}`}
            onClick={() => setBanner('STD')}
          >
            // STANDARD
          </button>
          <button
            type="button"
            className={`tab fp${banner === 'FRIEND' ? ' on' : ''}`}
            onClick={() => setBanner('FRIEND')}
          >
            // FRIEND FP {fpBalance}
          </button>
        </div>
      )}

      {banner === 'STD' ? (
        <div className={`sum-banner corner-ticks pity-${pityState}`}>
          <span className="tbl" />
          <span className="tbr" />
          <div className="grid" />
          <div className="banner-title">// BANNER.STD - STANDARD</div>
          <div className="banner-name">
            NETOPS DRIFTERS
            <span className="sub">all factions - chase power spikes - pity at {PITY_CAP}</span>
          </div>
          <div className="banner-art">
            <HeroPromoArt hero={featuredHero} className="promo-art promo-card" />
          </div>
        </div>
      ) : (
        <div className="sum-banner fp corner-ticks">
          <span className="tbl" />
          <span className="tbr" />
          <div className="grid" />
          <div className="banner-title">// BANNER.FP - FRIEND.NET</div>
          <div className="banner-name">
            WELCOME WAGON
            <span className="sub">earn FP by daily-pinging friends</span>
          </div>
          <div className="banner-art">
            <SilhouettePink />
          </div>
        </div>
      )}

      {banner === 'STD' && (
        <section className="sum-pressure">
          <div className="sum-pressure-head">
            <span className="sum-pressure-kicker">Close The Deal</span>
            <h2>Meta Pressure</h2>
          </div>
          <div className="sum-pressure-grid">
            {standardPressureCards.map((card) => (
              <article key={card.title} className="sum-pressure-card">
                <strong>{card.title}</strong>
                <p>{card.body}</p>
              </article>
            ))}
          </div>
          {featuredHero && (
            <div className="sum-featured-hook">
              <div className="sum-featured-body">
                <div className="sum-featured-copy">
                  <span className="sum-featured-kicker">Chase Unit</span>
                  <strong>{featuredHero.template.name}</strong>
                  <p>
                    Pulling higher-end operators like {featuredHero.template.name} is how a roster stops being cute and starts closing arena fights.
                  </p>
                </div>
                <div className="sum-featured-art">
                  <HeroPromoArt hero={featuredHero} className="promo-art promo-bust" />
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {banner === 'STD' ? (
        <div className={`sum-pity pity-${pityState}`}>
          <div className="row">
            <span className="label">
              PITY - <b>KERNEL_DUMP</b>
            </span>
            <span className="val">
              {pity}
              <span className="max">/{PITY_CAP}</span>
            </span>
          </div>
          <div className="bar">
            <span className="fill" style={{ width: `${pityPct}%` }} />
          </div>
          <div className="row sum-pity-note">
            <span>
              guaranteed <span className="sum-pity-emphasis">EPIC</span> at {PITY_CAP}
              {softHit && <span className="softpity"> - SOFT PITY +{Math.min(100, (pity - SOFT_PITY + 1) * 5)}% epic</span>}
            </span>
            <span>+{pullsToEpic} pulls</span>
          </div>
          <div className="sum-pity-callout">
            {pity >= 45
              ? 'Critical: the next click should feel expensive in a good way.'
              : softHit
                ? 'Soft pity online: this banner is officially warm.'
                : usingFreePull
                  ? 'Free pull loaded: take the free swing before spending shards.'
                  : 'Cold start: build the meter or wait for a better moment.'}
          </div>
        </div>
      ) : (
        <div className="sum-pity">
          <div className="row">
            <span className="label">
              FP.PITY - <b>WELCOME_WAGON</b>
            </span>
            <span className="val">
              {fpPity}
              <span className="max">/{fpCap}</span>
            </span>
          </div>
          <div className="bar">
            <span
              className="fill"
              style={{ width: `${fpPityPct}%`, background: 'linear-gradient(90deg, var(--lb-cyan), #ff79c6)' }}
            />
          </div>
          <div className="row sum-pity-note">
            <span>
              FP {fpBalance.toLocaleString()} balance - {fpCost} per pull
            </span>
            <span>+{Math.max(0, fpCap - fpPity)} pulls</span>
          </div>
        </div>
      )}

      {banner === 'STD' ? (
        <div className="sum-cta">
          <button type="button" className={`sum-btn tone-${x1Tone}`} disabled={!canX1} onClick={() => pull(1)}>
            {pulling ? '...' : usingFreePull ? 'FREE PULL x1' : 'SUMMON x1'}
            <span className="cost">
              {usingFreePull ? `${freeCredits} credit${freeCredits === 1 ? '' : 's'} loaded` : `${COST_X1} shards`}
            </span>
          </button>
          <button type="button" className={`sum-btn lg tone-${x10Tone}`} disabled={!canX10} onClick={() => pull(10)}>
            {pulling ? '...' : 'SUMMON x10'}
            <span className="cost">
              <b>{COST_X10} shards</b> - 1 guaranteed 4*+
            </span>
          </button>
        </div>
      ) : (
        <div className="sum-cta">
          <button
            type="button"
            className="sum-btn lg"
            style={{ gridColumn: '1 / -1', background: 'linear-gradient(180deg, #ff79c6, #c84a9b)', borderColor: '#ff79c6' }}
            disabled={!canFriendPull}
            onClick={pullFriend}
          >
            {pulling ? '...' : 'FRIEND PULL x1'}
            <span className="cost">
              <b>{fpCost} FP</b> - earn FP by pinging friends
            </span>
          </button>
        </div>
      )}

      <div className="sum-rates">
        <div className="row r">
          <span>
            <b>C</b> common
          </span>
          <span>65.0%</span>
        </div>
        <div className="row r">
          <span>
            <b>U</b> uncommon
          </span>
          <span>25.0%</span>
        </div>
        <div className="row r rare-row">
          <span>
            <b>R</b> rare
          </span>
          <span>8.0%</span>
        </div>
        <div className="row r l">
          <span>
            <b>L</b> legendary
          </span>
          <span>1.8%</span>
        </div>
        <div className="row r m">
          <span>
            <b>M</b> myth
          </span>
          <span>0.2%</span>
        </div>
      </div>

      {lastPull && lastPull.length > 0 && (
        <div className="sum-lastpull">
          <div className="h">
            <span>// last pull - {lastPull.length}x</span>
            <b>{lastPull.length} HEROES</b>
          </div>
          <div className="grid">
            {lastPull.map((hero, index) => (
              <div key={`${hero.id}-${index}`} className="cell" data-rar={hero.template.rarity}>
                <img
                  className="bust"
                  src={assetUrl(`/app/static/heroes/busts/${hero.template.code}.png`)}
                  alt={hero.template.name}
                  onError={(event) => {
                    ;(event.currentTarget as HTMLImageElement).style.display = 'none'
                  }}
                />
                <span className="rar">{RARITY_LETTER[hero.template.rarity] ?? '?'}</span>
                <span className="nm">{hero.template.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {revealState && (
        <SummonRevealOverlay
          outcomes={revealState.outcomes}
          pullCount={revealState.pullCount}
          onContinue={() => {
            navigate('/app/summon/results', { state: revealState })
            setRevealState(null)
          }}
        />
      )}
    </div>
  )
}

function SilhouettePurple() {
  return (
    <svg viewBox="0 0 120 150" style={{ width: '90%', height: '100%' }}>
      <ellipse cx="60" cy="142" rx="44" ry="6" fill="rgba(0,0,0,0.4)" />
      <g fill="var(--lb-purple)" opacity="0.7">
        <path d="M48 140 L 50 100 L 60 100 L 60 140 Z" />
        <path d="M72 140 L 70 100 L 60 100 L 60 140 Z" />
        <path d="M38 100 L 34 64 Q 34 54 44 50 L 76 50 Q 86 54 86 64 L 82 100 Z" />
        <path d="M42 56 Q 60 32 78 56 L 76 60 Q 60 44 44 60 Z" />
      </g>
      <line x1="52" y1="70" x2="58" y2="70" stroke="var(--lb-purple)" strokeWidth="2" />
      <line x1="62" y1="70" x2="68" y2="70" stroke="var(--lb-purple)" strokeWidth="2" />
      <rect x="46" y="86" width="28" height="3" fill="var(--lb-gold)" />
    </svg>
  )
}

function SilhouettePink() {
  return (
    <svg viewBox="0 0 120 150" style={{ width: '90%', height: '100%' }}>
      <ellipse cx="60" cy="142" rx="44" ry="6" fill="rgba(0,0,0,0.4)" />
      <g fill="#ff79c6" opacity="0.65">
        <path d="M48 140 L 50 100 L 60 100 L 60 140 Z" />
        <path d="M72 140 L 70 100 L 60 100 L 60 140 Z" />
        <path d="M38 100 L 34 64 Q 34 54 44 50 L 76 50 Q 86 54 86 64 L 82 100 Z" />
        <path d="M42 56 Q 60 32 78 56 L 76 60 Q 60 44 44 60 Z" />
      </g>
      <line x1="52" y1="70" x2="58" y2="70" stroke="#ff79c6" strokeWidth="2" />
      <line x1="62" y1="70" x2="68" y2="70" stroke="#ff79c6" strokeWidth="2" />
      <rect x="46" y="86" width="28" height="3" fill="var(--lb-cyan)" />
    </svg>
  )
}

export default SummonV2Route
