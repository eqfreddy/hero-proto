import { useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import type { Hero } from '../types'
import { useMe } from '../hooks/useMe'
import './Lobby.css'
import './SummonV2Results.css'

const RARITY_ORDER = ['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'MYTH']
const RARITY_LETTER: Record<string, string> = {
  COMMON: 'C',
  UNCOMMON: 'U',
  RARE: 'R',
  EPIC: 'E',
  LEGENDARY: 'L',
  MYTH: '★ M',
}
const RARITY_TIER: Record<string, string> = {
  COMMON: 'FLOPPY',
  UNCOMMON: 'HARD-DISK',
  RARE: 'SSD',
  EPIC: 'RAID-0',
  LEGENDARY: 'RAID-5',
  MYTH: 'LEGEN-WAIT-DARY',
}

interface ResultsState {
  heroes?: Hero[]
  pullCount?: number
}

export function SummonV2ResultsRoute() {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const state = location.state as ResultsState | null
  const heroes = state?.heroes ?? []
  const pullCount = state?.pullCount ?? heroes.length
  const faction = me?.faction ?? 'EXILE'

  const headliner = useMemo(() => {
    if (!heroes.length) return null
    return [...heroes].sort(
      (a, b) => RARITY_ORDER.indexOf(b.template.rarity) - RARITY_ORDER.indexOf(a.template.rarity),
    )[0]
  }, [heroes])

  const summary = useMemo(() => {
    const counts = { c: 0, u: 0, r: 0, e: 0, l: 0, m: 0 }
    for (const h of heroes) {
      switch (h.template.rarity) {
        case 'COMMON':    counts.c++; break
        case 'UNCOMMON':  counts.u++; break
        case 'RARE':      counts.r++; break
        case 'EPIC':      counts.e++; break
        case 'LEGENDARY': counts.l++; break
        case 'MYTH':      counts.m++; break
      }
    }
    const high = counts.e + counts.l + counts.m
    const mid = counts.r + counts.u
    return { high, mid, low: counts.c, total: heroes.length }
  }, [heroes])

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
          <Link className="link" to="/app/summon-v2">‹ BACK TO SUMMON</Link>
        </div>
        <nav className="lobby-bnav">
          <button type="button" className="item" onClick={() => navigate('/app/lobby')}>
            <span className="ico">H</span>HOME
          </button>
          <button type="button" className="item" onClick={() => navigate('/app/roster-v2')}>
            <span className="ico">R</span>ROSTER
          </button>
          <button type="button" className="item on" style={{ color: 'var(--lb-purple)' }}>
            <span className="ico summon">S</span>SUMMON
          </button>
          <button type="button" className="item" onClick={() => navigate('/app/battle-v2')}>
            <span className="ico">B</span>BATTLE
          </button>
          <button type="button" className="item" onClick={() => navigate('/app/shop')}>
            <span className="ico">$</span>SHOP
          </button>
        </nav>
      </div>
    )
  }

  const headlinerRarity = headliner.template.rarity
  const headlinerIsBig = ['EPIC', 'LEGENDARY', 'MYTH'].includes(headlinerRarity)
  const titleAccentClass =
    headlinerRarity === 'EPIC' ? 'accent epic'
    : headlinerRarity === 'MYTH' ? 'accent'
    : headlinerRarity === 'LEGENDARY' ? 'accent legend'
    : headlinerRarity === 'RARE' ? 'accent mid'
    : 'accent'

  return (
    <div className="lobby-root" data-faction={faction}>
      <div className="res-hdr">
        <div className="eyebrow">// {pullCount}× pull · complete</div>
        <div className="title">
          {headlinerRarity} <span className={titleAccentClass}>PULLED</span>
        </div>
      </div>

      <div className="res-hero" data-rar={headlinerRarity}>
        <div className="rays"></div>
        {headlinerIsBig && <div className="pulse"></div>}
        <div className="label">
          // {headlinerRarity} · {RARITY_TIER[headlinerRarity] ?? ''}
        </div>
        <div className="name">
          {headliner.template.name}
          <span className="sub">
            {headliner.template.faction} · {headliner.stars}★ · {headliner.template.role}
          </span>
        </div>
        <div className="fig-slot">
          <img
            className="bust"
            src={`/app/static/heroes/busts/${headliner.template.code}.png`}
            alt={headliner.template.name}
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        </div>
      </div>

      <div className="res-grid">
        {heroes.map((h, i) => (
          <div key={`${h.id}-${i}`} className="mini" data-rar={h.template.rarity}>
            <span className="rar-mark">{RARITY_LETTER[h.template.rarity] ?? '?'}</span>
            <div className="silhouette-mini">
              <img
                className="bust"
                src={`/app/static/heroes/busts/${h.template.code}.png`}
                alt={h.template.name}
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
              />
            </div>
            <div className="nm">{h.template.name}</div>
          </div>
        ))}
      </div>

      <div className="res-summary">
        <span>HIGH · <b className="new">{summary.high}</b></span>
        <span>MID · <b>{summary.mid}</b></span>
        <span>LOW · <b>{summary.low}</b></span>
      </div>

      <div className="res-cta">
        <button type="button" onClick={() => navigate('/app/roster-v2')}>VIEW ROSTER</button>
        <button
          type="button"
          className="primary"
          onClick={() => navigate('/app/summon-v2', { state: { repeat: pullCount } })}
        >
          {pullCount === 10 ? 'SUMMON ×10' : 'AGAIN'}
        </button>
      </div>

      <nav className="lobby-bnav">
        <button type="button" className="item" onClick={() => navigate('/app/lobby')}>
          <span className="ico">H</span>HOME
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/roster-v2')}>
          <span className="ico">R</span>ROSTER
        </button>
        <button type="button" className="item on" style={{ color: 'var(--lb-purple)' }}>
          <span className="ico summon">S</span>SUMMON
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/battle-v2')}>
          <span className="ico">B</span>BATTLE
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/shop')}>
          <span className="ico">$</span>SHOP
        </button>
      </nav>
    </div>
  )
}

export default SummonV2ResultsRoute
