import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { useStages } from '../hooks/useStages'
import { useQuery } from '@tanstack/react-query'
import { fetchDaily, type DailyQuest } from '../api/daily'
import type { Hero, Me, Stage } from '../types'
import './Lobby.css'

const RARITY_TIER: Record<string, string> = {
  COMMON: 'FLOPPY',
  UNCOMMON: 'HARD-DISK',
  RARE: 'SSD',
  EPIC: 'RAID-0',
  LEGENDARY: 'RAID-5',
  MYTH: 'LEGEN-WAIT-DARY',
}

function displayName(me: Me): string {
  const prefix = me.email.split('@')[0] ?? 'OPERATOR'
  return prefix.toUpperCase().replace(/[^A-Z0-9]/g, '-').slice(0, 14)
}

function fmtBig(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return String(n)
}

function pickFeatured(heroes: Hero[] | undefined): Hero | null {
  if (!heroes?.length) return null
  return [...heroes].sort((a, b) => b.power - a.power)[0]
}

function pickNextStage(stages: Stage[] | undefined): Stage | null {
  if (!stages?.length) return null
  const unlockedUncleared = stages.find((s) => s.unlocked && !s.cleared)
  if (unlockedUncleared) return unlockedUncleared
  return stages[stages.length - 1]
}

export function LobbyRoute() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: stages } = useStages()
  const { data: daily } = useQuery<DailyQuest[]>({
    queryKey: ['daily'],
    queryFn: fetchDaily,
    staleTime: 60_000,
    retry: 1,
  })

  const featured = useMemo(() => pickFeatured(heroes), [heroes])
  const nextStage = useMemo(() => pickNextStage(stages), [stages])

  if (!me) {
    return (
      <div className="lobby-root" data-faction="EXILE">
        <div className="lobby-hdr"><div className="player"><div className="who"><span className="name">LOADING</span></div></div></div>
      </div>
    )
  }

  const faction = me.faction
  const accent =
    faction === 'CORP_GREED' ? 'g'
    : faction === 'EXILE' ? 'p'
    : 'c'
  const dailyTop3 = (daily ?? []).slice(0, 3)
  const dailyDone = dailyTop3.filter((q) => q.status === 'CLAIMED' || q.progress >= q.goal).length

  return (
    <div className="lobby-root" data-faction={faction}>
      {/* header */}
      <div className="lobby-hdr">
        <div className="player">
          <svg className="badge" viewBox="0 0 32 32" style={{ overflow: 'visible' }}>
            <polygon points="16,3 28,10 28,22 16,29 4,22 4,10" fill="none" stroke="var(--lb-accent)" strokeWidth="2"/>
            <circle cx="16" cy="16" r="3" fill="var(--lb-accent)"/>
          </svg>
          <div className="who">
            <span className="name">{displayName(me)}</span>
            <span className="fac">{faction} · LV {me.account_level}</span>
          </div>
        </div>
        <div className="curr">
          <span className="c"><span className={`dot ${accent}`}></span>{me.energy}</span>
          <span className="c"><span className="dot p"></span>{fmtBig(me.gems)}</span>
          <span className="c"><span className="dot g"></span>{fmtBig(me.coins)}</span>
        </div>
      </div>

      {/* news ticker — placeholder for v1, no /news endpoint */}
      <div className="lobby-news">
        <span className="dot"></span>
        <span className="label">KERNEL_PANIC</span>
        <span>NODE.14 · resistance forces engaging</span>
        <span className="time">2h 47m</span>
      </div>

      {/* featured hero */}
      <div className="lobby-hero">
        <div className="lh-portrait">
          <div className="fig">
            {featured ? (
              <img
                className="bust"
                src={`/app/static/heroes/busts/${featured.template.code}.png`}
                alt={featured.template.name}
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <SilhouetteFallback />
            )}
          </div>
        </div>
        <div className="lh-info">
          {featured ? (
            <>
              <span className="name">{featured.template.name}</span>
              <span className="tier">
                {RARITY_TIER[featured.template.rarity] ?? featured.template.rarity} · {featured.template.role}{featured.template.attack_kind ? `-${featured.template.attack_kind}` : ''}
              </span>
              <div className="stats">
                <span className="k">ATK</span><span className="v c">{(featured.atk ?? 0).toLocaleString()}</span>
                <span className="k">DEF</span><span className="v">{(featured.def ?? 0).toLocaleString()}</span>
                <span className="k">SPD</span><span className="v p">{featured.spd ?? 0}</span>
                <span className="k">HP</span><span className="v">{(featured.hp ?? 0).toLocaleString()}</span>
              </div>
              <div
                className="deploy"
                role="button"
                tabIndex={0}
                onClick={() => navigate('/app/battle-v2')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate('/app/battle-v2') }}
              >
                DEPLOY
              </div>
            </>
          ) : (
            <>
              <span className="name">NO OPERATIVE</span>
              <span className="tier">ROSTER EMPTY · RECRUIT</span>
              <div className="stats">
                <span className="k">ATK</span><span className="v">—</span>
                <span className="k">DEF</span><span className="v">—</span>
                <span className="k">SPD</span><span className="v">—</span>
                <span className="k">HP</span><span className="v">—</span>
              </div>
              <div
                className="deploy recruit"
                role="button"
                tabIndex={0}
                onClick={() => navigate('/app/summon')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate('/app/summon') }}
              >
                RECRUIT
              </div>
            </>
          )}
        </div>
      </div>

      {/* daily tasks — hide entirely if endpoint failed */}
      {daily && dailyTop3.length > 0 && (
        <div className="lobby-tasks">
          <div className="h"><span>DAILY.queue</span><b>{dailyDone} of {dailyTop3.length}</b></div>
          {dailyTop3.map((q) => {
            const pct = Math.max(0, Math.min(100, Math.round((q.progress / Math.max(1, q.goal)) * 100)))
            const reward =
              q.reward_gems > 0 ? `+${q.reward_gems} ◇`
              : q.reward_coins > 0 ? `+${fmtBig(q.reward_coins)} ⬢`
              : q.reward_shards > 0 ? `+${q.reward_shards} ⬡`
              : ''
            const done = q.status === 'CLAIMED' || q.progress >= q.goal
            return (
              <div key={q.id} className={`row${done ? ' done' : ''}`} style={done ? { opacity: 0.55 } : undefined}>
                <span className="label">{q.target_key.replace(/_/g, ' ').toLowerCase()}</span>
                <span className="bar"><i style={{ width: `${pct}%` }}></i></span>
                <span className="reward">{reward}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* world map preview */}
      <div className="lobby-map" onClick={() => navigate('/app/battle-v2')}>
        <span className="label">
          <span className="dim">SECTOR</span> {nextStage?.code ?? '0x00'} · {RARITY_TIER[nextStage?.difficulty_tier ?? ''] ?? 'FLOPPY'}
        </span>
        <svg viewBox="0 0 280 90" style={{ width: '100%', height: '100%' }}>
          <defs>
            <pattern id="grid-lobby" width="14" height="14" patternUnits="userSpaceOnUse">
              <path d="M 14 0 L 0 0 0 14" fill="none" stroke="rgba(0,255,224,0.07)" strokeWidth="1"/>
            </pattern>
          </defs>
          <rect width="280" height="90" fill="url(#grid-lobby)"/>
          <g stroke="var(--lb-accent-stroke)" strokeWidth="1.5" fill="none">
            <path d="M 20 70 L 70 70 L 100 50 L 150 50 L 180 30 L 240 30"/>
            <path d="M 100 50 L 100 30 L 80 18"/>
          </g>
          <g>
            <polygon points="70,70 78,74 78,82 70,86 62,82 62,74" fill="#04060c" stroke="var(--lb-accent-stroke)" strokeWidth="1"/>
            <polygon points="150,50 158,54 158,62 150,66 142,62 142,54" fill="#04060c" stroke="var(--lb-accent-stroke)" strokeWidth="1"/>
            <circle cx="180" cy="30" r="14" fill="var(--lb-accent-soft)"/>
            <polygon points="180,18 195,26 195,42 180,50 165,42 165,26" fill="var(--lb-accent-soft)" stroke="var(--lb-accent)" strokeWidth="1.5"/>
            <polygon points="180,24 188,28 188,40 180,44 172,40 172,28" fill="var(--lb-accent)"/>
            <polygon points="240,30 248,34 248,42 240,46 232,42 232,34" fill="#04060c" stroke="var(--lb-accent-stroke)" strokeWidth="1" strokeDasharray="2 2"/>
          </g>
          <text x="180" y="58" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="6.5" fill="var(--lb-accent)" letterSpacing="1">
            {(nextStage?.code ?? 'NODE.14').toUpperCase()}
          </text>
        </svg>
      </div>

    </div>
  )
}

function SilhouetteFallback() {
  return (
    <svg viewBox="0 0 120 150" style={{ width: '80%', height: '90%' }}>
      <ellipse cx="60" cy="140" rx="42" ry="6" fill="rgba(0,0,0,0.4)"/>
      <g fill="var(--lb-accent)" opacity="0.55">
        <path d="M48 138 L 50 100 L 60 100 L 60 138 Z"/>
        <path d="M72 138 L 70 100 L 60 100 L 60 138 Z"/>
        <path d="M40 100 L 36 70 Q 36 60 44 56 L 76 56 Q 84 60 84 70 L 80 100 Z"/>
        <path d="M44 60 Q 60 40 76 60 L 74 64 Q 60 50 46 64 Z"/>
      </g>
      <line x1="52" y1="70" x2="58" y2="70" stroke="var(--lb-accent)" strokeWidth="2"/>
      <line x1="62" y1="70" x2="68" y2="70" stroke="var(--lb-accent)" strokeWidth="2"/>
      <rect x="48" y="86" width="24" height="3" fill="var(--lb-gold)"/>
    </svg>
  )
}

export default LobbyRoute
