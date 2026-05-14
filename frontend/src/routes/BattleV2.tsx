import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { useStages } from '../hooks/useStages'
import { postBattle } from '../api/battles'
import { toast } from '../store/ui'
import type { Hero, Stage } from '../types'
import './Lobby.css'
import './BattleV2.css'

function pickStage(stages: Stage[] | undefined): Stage | null {
  if (!stages?.length) return null
  return stages.find((s) => s.unlocked && !s.cleared) ?? stages[0]
}

function pickTeam(heroes: Hero[] | undefined, n = 3): Hero[] {
  if (!heroes?.length) return []
  return [...heroes].sort((a, b) => b.power - a.power).slice(0, n)
}

export function BattleV2Route() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: stages } = useStages()
  const [deploying, setDeploying] = useState(false)
  const [selectedAlly, setSelectedAlly] = useState<number | null>(null)

  const stage = useMemo(() => pickStage(stages), [stages])
  const team = useMemo(() => pickTeam(heroes), [heroes])
  const faction = me?.faction ?? 'EXILE'

  async function deploy() {
    if (!stage || team.length === 0 || deploying) return
    setDeploying(true)
    try {
      const battle = await postBattle({
        stage_id: stage.id,
        team: team.map((h) => h.id),
      })
      navigate(`/battle/${battle.id}/replay`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'deploy failed')
      setDeploying(false)
    }
  }

  if (!heroes || !stages) {
    return (
      <div className="lobby-root" data-faction={faction}>
        <div className="bat-hud"><span>LOADING…</span></div>
      </div>
    )
  }

  if (!stage || team.length === 0) {
    return (
      <div className="lobby-root" data-faction={faction}>
        <div className="bat-hud">
          <span>{!stage ? 'NO STAGE' : 'NO TEAM'}</span>
          <span className="turn">DEPLOY · <b>—</b></span>
        </div>
        <div className="bat-empty">
          {team.length === 0
            ? 'NO HEROES IN ROSTER'
            : 'NO STAGE UNLOCKED'}
          <br />
          <span className="link" onClick={() => navigate(team.length === 0 ? '/app/summon-v2' : '/app/lobby')}>
            ‹ {team.length === 0 ? 'GO TO SUMMON' : 'BACK TO LOBBY'}
          </span>
        </div>
        <nav className="lobby-bnav">
          <button type="button" className="item" onClick={() => navigate('/app/lobby')}><span className="ico">H</span>HOME</button>
          <button type="button" className="item" onClick={() => navigate('/app/roster-v2')}><span className="ico">R</span>ROSTER</button>
          <button type="button" className="item" onClick={() => navigate('/app/summon-v2')}><span className="ico summon">S</span>SUMMON</button>
          <button type="button" className="item on"><span className="ico">B</span>BATTLE</button>
          <button type="button" className="item" onClick={() => navigate('/app/shop')}><span className="ico">$</span>SHOP</button>
        </nav>
      </div>
    )
  }

  const teamPower = team.reduce((s, h) => s + h.power, 0)
  const recPower = stage.recommended_power ?? 0
  const delta = teamPower - recPower
  const turnNo = (me?.stages_cleared?.length ?? 0) + 1

  return (
    <div className="lobby-root" data-faction={faction}>
      <div className="bat-hud">
        <span>{stage.code.toUpperCase()} · {stage.display_name?.toUpperCase() ?? 'OUTAGE'}</span>
        <span className="turn">RUN · <b>{String(turnNo).padStart(2, '0')}</b> · LOADOUT</span>
      </div>

      <div className="bat-stage">
        <span className="label-cnr">STAGE · <b>{stage.code}</b></span>
        <span className="tel-cnr">
          REC.PWR · <span className="ok">{recPower.toLocaleString()}</span><br/>
          YOUR.PWR · <span style={{ color: delta >= 0 ? 'var(--lb-cyan)' : 'var(--lb-crimson)' }}>{teamPower.toLocaleString()}</span>
        </span>
        <svg viewBox="0 0 320 180" preserveAspectRatio="xMidYMid meet">
          <defs>
            <pattern id="grid-bat" width="16" height="16" patternUnits="userSpaceOnUse">
              <path d="M 16 0 L 0 0 0 16" fill="none" stroke="rgba(0,255,224,0.06)" strokeWidth="1"/>
            </pattern>
            <radialGradient id="impact-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#00ffe0" stopOpacity="0.9"/>
              <stop offset="100%" stopColor="#00ffe0" stopOpacity="0"/>
            </radialGradient>
          </defs>
          <rect width="320" height="180" fill="url(#grid-bat)"/>
          <g stroke="rgba(0,255,224,0.4)" strokeWidth="1.5" fill="none">
            <path d="M 30 90 L 90 90 L 130 60 L 200 60 L 240 90 L 290 90"/>
            <path d="M 130 60 L 130 120 L 90 130"/>
            <path d="M 200 60 L 240 30"/>
          </g>
          {/* enemy slots (top) */}
          <g>
            <polygon points="90,40 105,48 105,62 90,70 75,62 75,48" fill="#150505" stroke="rgba(200,16,46,0.55)" strokeWidth="1.5"/>
            <polygon points="160,30 178,40 178,58 160,68 142,58 142,40" fill="#1a1408" stroke="var(--lb-gold)" strokeWidth="2"/>
            <polygon points="230,40 245,48 245,62 230,70 215,62 215,48" fill="#150505" stroke="rgba(200,16,46,0.55)" strokeWidth="1.5"/>
            <rect x="155" y="44" width="10" height="10" fill="var(--lb-gold)"/>
          </g>
          {/* ally slots (bottom) */}
          <g>
            <circle cx="90" cy="140" r="22" fill="url(#impact-glow)" opacity="0.6"/>
            <polygon points="90,120 105,128 105,142 90,150 75,142 75,128" fill="rgba(0,255,224,0.08)" stroke="#00ffe0" strokeWidth="2"/>
            <polygon points="90,126 100,132 100,140 90,146 80,140 80,132" fill="#00ffe0"/>
            <polygon points="160,128 175,136 175,150 160,158 145,150 145,136" fill="#06101a" stroke="rgba(0,255,224,0.7)" strokeWidth="1.5"/>
            <polygon points="230,128 245,136 245,150 230,158 215,150 215,136" fill="#06101a" stroke="rgba(0,255,224,0.7)" strokeWidth="1.5"/>
          </g>
          {/* attack arc preview */}
          <path d="M 90 120 Q 130 80 160 50" stroke="#00ffe0" strokeWidth="1.5" strokeDasharray="4 3" fill="none" opacity="0.6"/>
          <circle cx="160" cy="50" r="3" fill="#00ffe0" opacity="0.6"/>
          <text x="172" y="34" fontFamily="Space Grotesk" fontWeight="700" fontSize="14" fill="var(--lb-gold)">
            {delta >= 0 ? `+${delta.toLocaleString()}` : delta.toLocaleString()}
          </text>
          <text x="172" y="44" fontFamily="JetBrains Mono" fontSize="6" fill="var(--lb-gold)" letterSpacing="1">PWR Δ</text>
        </svg>
      </div>

      <div className="bat-enemies">
        <div className="enemy">
          <span className="lvtag">L?</span>
          <div className="por-mini"><div className="fig"></div></div>
          <div className="hp-mini"><span className="f" style={{ width: '100%' }}></span></div>
          <div className="nm">UNKNOWN</div>
        </div>
        <div className="enemy" data-st="boss">
          <span className="lvtag">L? ★</span>
          <div className="por-mini"><div className="fig"></div></div>
          <div className="hp-mini"><span className="f" style={{ width: '100%' }}></span></div>
          <div className="nm">BOSS</div>
        </div>
        <div className="enemy">
          <span className="lvtag">L?</span>
          <div className="por-mini"><div className="fig"></div></div>
          <div className="hp-mini"><span className="f" style={{ width: '100%' }}></span></div>
          <div className="nm">UNKNOWN</div>
        </div>
      </div>

      <div className="bat-team">
        {team.map((h) => {
          const isSel = h.id === selectedAlly
          const hp = h.hp ?? 0
          const energyPct = Math.min(100, (h.level / 50) * 100)
          return (
            <div
              key={h.id}
              className={`ally${isSel ? ' sel' : ''}`}
              onClick={() => setSelectedAlly(isSel ? null : h.id)}
            >
              <div className="por-mini">
                <img
                  src={`/app/static/heroes/busts/${h.template.code}.png`}
                  alt={h.template.name}
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                />
              </div>
              <div className="nm">{h.template.name}</div>
              <div className="hp"><span className="f" style={{ width: '100%' }}></span></div>
              <div className="ene"><span className="f" style={{ width: `${energyPct}%` }}></span></div>
              <div className="vals">
                <span className="cyan">{hp.toLocaleString()} hp</span>
                <span className="purp">L{h.level}</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="bat-actions">
        <button type="button" className="bat-cancel" onClick={() => navigate('/app/lobby')}>‹ ABORT</button>
        <button type="button" className="bat-deploy" disabled={deploying} onClick={deploy}>
          {deploying ? '...' : 'DEPLOY'}
        </button>
      </div>

      <nav className="lobby-bnav">
        <button type="button" className="item" onClick={() => navigate('/app/lobby')}><span className="ico">H</span>HOME</button>
        <button type="button" className="item" onClick={() => navigate('/app/roster-v2')}><span className="ico">R</span>ROSTER</button>
        <button type="button" className="item" onClick={() => navigate('/app/summon-v2')}><span className="ico summon">S</span>SUMMON</button>
        <button type="button" className="item on"><span className="ico">B</span>BATTLE</button>
        <button type="button" className="item" onClick={() => navigate('/app/shop')}><span className="ico">$</span>SHOP</button>
      </nav>
    </div>
  )
}

export default BattleV2Route
