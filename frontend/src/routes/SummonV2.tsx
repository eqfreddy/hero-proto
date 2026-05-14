import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { pullStandard } from '../api/summon'
import { toast } from '../store/ui'
import type { Hero } from '../types'
import './Lobby.css'
import './SummonV2.css'

const PITY_CAP = 50
const SOFT_PITY = 35
const COST_X1 = 1
const COST_X10 = 10

const RARITY_LETTER: Record<string, string> = {
  COMMON: 'C',
  UNCOMMON: 'U',
  RARE: 'R',
  EPIC: 'E',
  LEGENDARY: 'L',
  MYTH: 'M',
}

export function SummonV2Route() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const [pulling, setPulling] = useState(false)
  const [lastPull, setLastPull] = useState<Hero[] | null>(null)

  const pity = me?.pulls_since_epic ?? 0
  const pityPct = Math.min(100, (pity / PITY_CAP) * 100)
  const pullsToEpic = Math.max(0, PITY_CAP - pity)
  const softHit = pity >= SOFT_PITY
  const shards = me?.shards ?? 0
  const canX1 = shards >= COST_X1 && !pulling
  const canX10 = shards >= COST_X10 && !pulling

  const featuredHero = useMemo(() => {
    if (!heroes?.length) return null
    const rare = heroes.find((h) =>
      ['EPIC', 'LEGENDARY', 'MYTH'].includes(h.template.rarity),
    )
    return rare ?? null
  }, [heroes])

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
      navigate('/app/summon/results', { state: { heroes: res.heroes, pullCount: count } })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'pull failed')
    } finally {
      setPulling(false)
    }
  }

  return (
    <div className="lobby-root" data-faction={faction}>
      {/* header */}
      <div className="sum-hdr">
        <button type="button" className="back" onClick={() => navigate('/app/lobby')}>‹ LOBBY</button>
        <span className="title">SUMMON.exe</span>
        <span className="right">
          <span className="pill">{shards.toLocaleString()} ✦</span>
        </span>
      </div>

      {/* banner */}
      <div className="sum-banner corner-ticks">
        <span className="tbl"></span><span className="tbr"></span>
        <div className="grid"></div>
        <div className="banner-title">// BANNER.STD · STANDARD</div>
        <div className="banner-name">
          NETOPS DRIFTERS
          <span className="sub">all factions · pity at {PITY_CAP} pulls</span>
        </div>
        <div className="banner-art">
          {featuredHero ? (
            <img
              className="bust"
              src={`/app/static/heroes/busts/${featuredHero.template.code}.png`}
              alt={featuredHero.template.name}
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <SilhouettePurple />
          )}
        </div>
      </div>

      {/* pity */}
      <div className="sum-pity">
        <div className="row">
          <span className="label">PITY · <b>KERNEL_DUMP</b></span>
          <span className="val">{pity}<span className="max">/{PITY_CAP}</span></span>
        </div>
        <div className="bar"><span className="fill" style={{ width: `${pityPct}%` }}></span></div>
        <div className="row" style={{ marginTop: 6, fontSize: 8.5, letterSpacing: '0.16em' }}>
          <span>
            guaranteed <span style={{ color: 'var(--lb-purple)' }}>EPIC</span> at {PITY_CAP}
            {softHit && <span className="softpity"> · SOFT PITY +{Math.min(100, (pity - SOFT_PITY + 1) * 5)}% epic</span>}
          </span>
          <span>+{pullsToEpic} pulls</span>
        </div>
      </div>

      {/* CTAs */}
      <div className="sum-cta">
        <button
          type="button"
          className="sum-btn"
          disabled={!canX1}
          onClick={() => pull(1)}
        >
          {pulling ? '…' : 'SUMMON ×1'}
          <span className="cost">{COST_X1} ✦</span>
        </button>
        <button
          type="button"
          className="sum-btn lg"
          disabled={!canX10}
          onClick={() => pull(10)}
        >
          {pulling ? '…' : 'SUMMON ×10'}
          <span className="cost"><b>{COST_X10} ✦</b> · 1 GUARANTEED 4★+</span>
        </button>
      </div>

      {/* rates */}
      <div className="sum-rates">
        <div className="row r"><span><b>C</b> common</span><span>65.0%</span></div>
        <div className="row r"><span><b>U</b> uncommon</span><span>25.0%</span></div>
        <div className="row r rare-row"><span><b>R</b> rare</span><span>8.0%</span></div>
        <div className="row r l"><span><b>L</b> legendary</span><span>1.8%</span></div>
        <div className="row r m"><span><b>M</b> myth</span><span>0.2%</span></div>
      </div>

      {/* inline last-pull preview */}
      {lastPull && lastPull.length > 0 && (
        <div className="sum-lastpull">
          <div className="h">
            <span>// last pull · {lastPull.length}x</span>
            <b>{lastPull.length} HEROES</b>
          </div>
          <div className="grid">
            {lastPull.map((h, i) => (
              <div key={`${h.id}-${i}`} className="cell" data-rar={h.template.rarity}>
                <img
                  className="bust"
                  src={`/app/static/heroes/busts/${h.template.code}.png`}
                  alt={h.template.name}
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                />
                <span className="rar">{RARITY_LETTER[h.template.rarity] ?? '?'}</span>
                <span className="nm">{h.template.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* bottom nav */}
      <nav className="lobby-bnav">
        <button type="button" className="item" onClick={() => navigate('/app/lobby')}>
          <span className="ico">H</span>HOME
        </button>
        <button type="button" className="item" onClick={() => navigate('/app/roster')}>
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

function SilhouettePurple() {
  return (
    <svg viewBox="0 0 120 150" style={{ width: '90%', height: '100%' }}>
      <ellipse cx="60" cy="142" rx="44" ry="6" fill="rgba(0,0,0,0.4)"/>
      <g fill="var(--lb-purple)" opacity="0.7">
        <path d="M48 140 L 50 100 L 60 100 L 60 140 Z"/>
        <path d="M72 140 L 70 100 L 60 100 L 60 140 Z"/>
        <path d="M38 100 L 34 64 Q 34 54 44 50 L 76 50 Q 86 54 86 64 L 82 100 Z"/>
        <path d="M42 56 Q 60 32 78 56 L 76 60 Q 60 44 44 60 Z"/>
      </g>
      <line x1="52" y1="70" x2="58" y2="70" stroke="var(--lb-purple)" strokeWidth="2"/>
      <line x1="62" y1="70" x2="68" y2="70" stroke="var(--lb-purple)" strokeWidth="2"/>
      <rect x="46" y="86" width="28" height="3" fill="var(--lb-gold)"/>
    </svg>
  )
}

export default SummonV2Route
