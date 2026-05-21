import { useEffect, useMemo } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { useStages } from '../hooks/useStages'
import { useGuild } from '../hooks/useGuild'
import { useRaid } from '../hooks/useRaid'
import { fetchDaily, type DailyQuest } from '../api/daily'
import { fetchBattlePass, type BPState } from '../api/battlePass'
import { useSoundStore } from '../store/sound'
import type { Hero, Stage } from '../types'
import { assetUrl } from '../api/client'
import './Lobby.css'

const RARITY_TIER: Record<string, string> = {
  COMMON: 'FLOPPY',
  UNCOMMON: 'HARD-DISK',
  RARE: 'SSD',
  EPIC: 'RAID-0',
  LEGENDARY: 'RAID-5',
  MYTH: 'LEGEN-WAIT-DARY',
}
const TIER_SHORT: Record<string, string> = {
  COMMON: 'FL', UNCOMMON: 'HD', RARE: 'SD', EPIC: 'R0', LEGENDARY: 'R5', MYTH: 'LW',
}

function fmtBig(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`
  return String(n)
}
function topByPower(heroes: Hero[] | undefined, count: number): Hero[] {
  if (!heroes?.length) return []
  return [...heroes].sort((a, b) => b.power - a.power).slice(0, count)
}
function pickNextStage(stages: Stage[] | undefined): Stage | null {
  if (!stages?.length) return null
  const unclearedUnlocked = stages.find((s) => s.unlocked && !s.cleared)
  return unclearedUnlocked ?? stages[stages.length - 1]
}

export function LobbyRoute() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: stages } = useStages()
  const { data: guildData } = useGuild()
  const { data: raid } = useRaid()
  const { data: daily } = useQuery<DailyQuest[]>({
    queryKey: ['daily'], queryFn: fetchDaily, staleTime: 60_000, retry: 1,
  })
  const { data: bp } = useQuery<BPState>({
    queryKey: ['battle-pass'], queryFn: fetchBattlePass, staleTime: 120_000, retry: 1,
  })
  const playBgm = useSoundStore((s) => s.playBgm)

  useEffect(() => { playBgm('ancient_map') }, [playBgm])

  const featured = useMemo(() => topByPower(heroes, 1)[0] ?? null, [heroes])
  const rosterTop = useMemo(() => topByPower(heroes, 6), [heroes])
  const nextStage = useMemo(() => pickNextStage(stages), [stages])
  const dailyTop = (daily ?? []).slice(0, 3)
  const dailyDone = dailyTop.filter((q) => q.status === 'CLAIMED' || q.progress >= q.goal).length
  const guild = guildData?.guild ?? null
  const guildSub = guild ? `${guild.member_count} members` : 'Join for raids'
  const raidSub = raid ? `Raid ${String(raid.state).toLowerCase()}` : 'No active raid'
  const guildRaidSub = raid ? `${raid.boss_name} · ${raid.tier} · ${String(raid.state).toLowerCase()}` : guildSub

  if (!me) {
    return (
      <div className="lb3">
        <div className="lb3-shell">
          <header className="lb3-topbar"><div className="lb3-brand">HERO<em>·</em>PROTO <span className="sub">// LOADING</span></div></header>
        </div>
      </div>
    )
  }

  const tierLabel = featured ? (RARITY_TIER[featured.template.rarity] ?? featured.template.rarity) : '—'

  return (
    <div className="lb3">
      <div className="lb3-shell">

        {/* TOPBAR removed — Shell's TopNav handles player + currencies now */}

        {/* ═══ TICKER ═══ */}
        <div className="lb3-ticker">
          <div className="lb3-ticker-dot" />
          <span className="lb3-ticker-tag">Incident</span>
          <div className="lb3-ticker-wrap">
            <div className="lb3-ticker-scroll">
              <span><em>{nextStage?.code ?? 'NODE.14'}</em> · resistance forces engaging · TIER-{((nextStage?.order ?? 14) % 5) + 1} INCIDENT active ·&nbsp;</span>
              <span>ALERT: CORP_GREED audit-bots deployed to SECTOR-7 ·&nbsp;</span>
              <span>SHADOW_IT infiltration successful — 2 servers liberated ·&nbsp;</span>
              <span>Guild [NULL_POINTER] cleared RAID-5 ·&nbsp;</span>
              <span><em>{nextStage?.code ?? 'NODE.14'}</em> · resistance forces engaging · TIER-{((nextStage?.order ?? 14) % 5) + 1} INCIDENT active ·&nbsp;</span>
              <span>ALERT: CORP_GREED audit-bots deployed to SECTOR-7 ·&nbsp;</span>
              <span>SHADOW_IT infiltration successful — 2 servers liberated ·&nbsp;</span>
              <span>Guild [NULL_POINTER] cleared RAID-5 ·&nbsp;</span>
            </div>
          </div>
          <span className="lb3-ticker-time">T+{Math.floor(Math.random() * 4) + 1}h {Math.floor(Math.random() * 60).toString().padStart(2, '0')}m</span>
        </div>

        {/* SIDENAV removed — Shell's PlayNav handles primary navigation now.
            Secondary destinations (Guild, Raids, BP, Friends, Events) are
            promoted to the tile grid below the hero panel. */}

        {/* ═══ MAIN ═══ */}
        <main className="lb3-main">

          {/* HERO PANEL */}
          <div className="lb3-hero">
            <div className="lb3-hero-visual">
              {featured ? (
                <img
                  className="lb3-hero-bust"
                  src={assetUrl(`/app/static/heroes/busts/${featured.template.code}.png`)}
                  alt={featured.template.name}
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                />
              ) : (
                <HeroSilhouette />
              )}
            </div>
            <div className="lb3-hero-info">
              <div className="lb3-hero-eyebrow">
                <span className="ln" />
                <span className="lb3-tier-pill">{tierLabel}</span>
                {featured ? 'Specialist' : 'Vacancy'}
              </div>
              <div className="lb3-hero-name">{featured ? featured.template.name : 'NO OPERATIVE'}</div>
              <div className="lb3-hero-role">
                {featured
                  ? `${featured.template.role}${featured.template.attack_kind ? ' · ' + featured.template.attack_kind : ''} · ${me.faction}`
                  : 'Roster empty · recruit to begin'}
              </div>
              <div className="lb3-hero-stats">
                <div className="lb3-stat"><span className="lb3-stat-lbl">ATK</span><span className="lb3-stat-val atk">{featured ? (featured.atk ?? 0).toLocaleString() : '—'}</span></div>
                <div className="lb3-stat"><span className="lb3-stat-lbl">DEF</span><span className="lb3-stat-val">{featured ? (featured.def ?? 0).toLocaleString() : '—'}</span></div>
                <div className="lb3-stat"><span className="lb3-stat-lbl">SPD</span><span className="lb3-stat-val spd">{featured ? featured.spd ?? 0 : '—'}</span></div>
                <div className="lb3-stat"><span className="lb3-stat-lbl">HP</span><span className="lb3-stat-val">{featured ? (featured.hp ?? 0).toLocaleString() : '—'}</span></div>
              </div>
              <div className="lb3-power-row">
                <span className="lb3-power-lbl">Combat Power</span>
                <span className="lb3-power-val">{featured ? featured.power.toLocaleString() : '—'}</span>
              </div>
              <button
                className="lb3-deploy"
                onClick={() => navigate(featured ? '/app/stages' : '/app/summon')}
              >
                {featured ? 'Continue Campaign' : 'Recruit Operative'}
              </button>
            </div>
          </div>

          {/* TILE GRID — primary shortcuts. 2×3 fat tiles. */}
          <div className="lb3-tiles">
            <button className="lb3-tile" onClick={() => navigate('/app/arena')}>
              <span className="ico">⚔</span>
              <span className="lbl">Arena</span>
              <span className="sub">PvP</span>
            </button>
            <button className="lb3-tile" onClick={() => navigate('/app/guild')}>
              <span className="ico">🛡</span>
              <span className="lbl">Guild</span>
              <span className="sub">{guildSub}</span>
            </button>
            <button className="lb3-tile" onClick={() => navigate('/app/raids')}>
              <span className="ico">🐉</span>
              <span className="lbl">Raids</span>
              <span className="sub">{raidSub}</span>
            </button>
            <button className="lb3-tile" onClick={() => navigate('/app/battle-pass')}>
              <span className="ico">🎟</span>
              <span className="lbl">Battle Pass</span>
              <span className="sub">{bp?.progress ? `T${bp.progress.current_tier}` : '—'}</span>
            </button>
            <button className="lb3-tile" onClick={() => navigate('/app/friends')}>
              <span className="ico">👥</span>
              <span className="lbl">Friends</span>
              <span className="sub">Mail</span>
            </button>
            <button className="lb3-tile" onClick={() => navigate('/app/event')}>
              <span className="ico">🎁</span>
              <span className="lbl">Events</span>
              <span className="sub">Live</span>
            </button>
          </div>

          {/* DAILY */}
          {daily && dailyTop.length > 0 && (
            <div>
              <div className="lb3-secthead">
                <span className="title">Daily.queue</span>
                <span className={'meta' + (dailyDone < dailyTop.length ? ' dim' : '')}>{dailyDone} / {dailyTop.length} Complete</span>
              </div>
              <div className="lb3-daily">
                {dailyTop.map((q) => {
                  const pct = Math.max(0, Math.min(100, Math.round((q.progress / Math.max(1, q.goal)) * 100)))
                  const done = q.status === 'CLAIMED' || q.progress >= q.goal
                  const reward =
                    q.reward_gems > 0 ? `+${q.reward_gems} ◇`
                    : q.reward_coins > 0 ? `+${fmtBig(q.reward_coins)} ⬢`
                    : q.reward_shards > 0 ? `+${q.reward_shards} ⬡`
                    : ''
                  return (
                    <div key={q.id} className={'lb3-quest' + (done ? ' done' : '')}>
                      <div className="lb3-quest-ico">
                        {done ? (
                          <svg viewBox="0 0 14 14" width="13" height="13"><polyline points="2,7 5,11 12,3" fill="none" stroke="var(--good)" strokeWidth="1.5"/></svg>
                        ) : (
                          <svg viewBox="0 0 14 14" width="13" height="13"><rect x="2" y="3" width="10" height="8" fill="none" stroke="currentColor" strokeWidth="1.2"/><line x1="5" y1="6" x2="9" y2="6" stroke="currentColor" strokeWidth="1"/></svg>
                        )}
                      </div>
                      <div className="lb3-quest-body">
                        <span className="lb3-quest-name">{q.target_key.replace(/_/g, ' ').toLowerCase()}</span>
                        <div className="lb3-quest-track"><div className="lb3-quest-fill" style={{ width: `${pct}%` }} /></div>
                      </div>
                      <span className="lb3-quest-reward">{reward}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* MAP */}
          <div>
            <div className="lb3-secthead">
              <span className="title">World Map · Active Sector</span>
            </div>
            <div className="lb3-map" onClick={() => navigate('/app/stages')}>
              <div className="lb3-map-header">
                <div>
                  <div className="lb3-map-title">{nextStage?.code ?? 'NODE.??'} · {RARITY_TIER[nextStage?.difficulty_tier ?? ''] ?? 'INCIDENT'}</div>
                  <div className="lb3-map-sub">Sector {Math.floor((nextStage?.order ?? 0) / 5) + 1} · Datacenter Incursion</div>
                </div>
                <button className="lb3-map-btn" onClick={(e) => { e.stopPropagation(); navigate('/app/stages') }}>Enter Sector →</button>
              </div>
              <MapSVG nextCode={nextStage?.code ?? 'N.14'} />
            </div>
          </div>

        </main>

        {/* ═══ ASIDE ═══ */}
        <aside className="lb3-aside">

          {/* ROSTER */}
          <div>
            <div className="lb3-secthead">
              <span className="title">Active Roster</span>
              <span className="meta dim">{(heroes?.length ?? 0).toString()} / 30</span>
            </div>
            <div className="lb3-roster">
              {rosterTop.map((h, idx) => (
                <NavLink
                  key={h.id}
                  to={`/app/roster/${h.id}`}
                  className={'lb3-roster-card' + (idx === 0 ? ' is-active' : '')}
                  title={h.template.name}
                >
                  <img
                    className="lb3-roster-bust"
                    src={assetUrl(`/app/static/heroes/busts/${h.template.code}.png`)}
                    alt={h.template.name}
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                  />
                  <span className="lb3-roster-name">{h.template.name}</span>
                  <div className="lb3-roster-tier">{TIER_SHORT[h.template.rarity] ?? '·'}</div>
                </NavLink>
              ))}
              {rosterTop.length === 0 && (
                <div style={{ gridColumn: '1 / -1', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', letterSpacing: '0.15em', textAlign: 'center', padding: '18px 0' }}>
                  NO OPERATIVES — VISIT /SUMMON
                </div>
              )}
            </div>
          </div>

          <div style={{ height: 1, background: 'var(--border)' }} />

          {/* BATTLE PASS */}
          <div className="lb3-card">
            <div className="lb3-card-head">Battle Pass{bp?.season ? ` · ${bp.season.code}` : ''}</div>
            {bp?.season && bp.progress ? (
              <>
                <div className="lb3-bp-bar">
                  <div className="lb3-bp-fill" style={{ width: `${Math.min(100, Math.round((bp.progress.current_tier / bp.season.max_tier) * 100))}%` }} />
                </div>
                <div className="lb3-bp-meta">
                  <span>Tier <strong>{bp.progress.current_tier}</strong> / {bp.season.max_tier}</span>
                  <span><strong>{fmtBig(bp.progress.xp_total)}</strong> XP</span>
                </div>
              </>
            ) : (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', letterSpacing: '0.15em' }}>NO ACTIVE SEASON</div>
            )}
          </div>

          {/* EVENTS — placeholder until /events is wired */}
          <div className="lb3-card">
            <div className="lb3-card-head">Active Events</div>
            <div className="lb3-events">
              <div className="lb3-event">
                <div className="lb3-event-marker" style={{ background: 'var(--crimson)' }} />
                <div style={{ flex: 1 }}>
                  <div className="lb3-event-name">KERNEL_PANIC WEEK</div>
                  <div className="lb3-event-time">ENDS IN 2d 14h</div>
                </div>
              </div>
              <div className="lb3-event">
                <div className="lb3-event-marker" style={{ background: 'var(--purple)' }} />
                <div style={{ flex: 1 }}>
                  <div className="lb3-event-name">SHARD DOUBLE-DROP</div>
                  <div className="lb3-event-time">ENDS IN 6h 22m</div>
                </div>
              </div>
              <div className="lb3-event">
                <div className="lb3-event-marker" style={{ background: 'var(--gold)' }} />
                <div style={{ flex: 1 }}>
                  <div className="lb3-event-name">GUILD SEASON END</div>
                  <div className="lb3-event-time">ENDS IN 4d 8h</div>
                </div>
              </div>
            </div>
          </div>

          {/* GUILD */}
          <div className="lb3-card" onClick={() => navigate('/app/guild')} style={{ cursor: 'pointer' }}>
            <div className="lb3-card-head">Guild</div>
            <div className="lb3-guild">
              <svg className="lb3-guild-shield" viewBox="0 0 36 40">
                <path d="M18 3 L32 9 L32 23 Q32 34 18 38 Q4 34 4 23 L4 9 Z" fill="var(--gold-bg)" stroke="var(--gold-bdr)" strokeWidth="1.5"/>
                <text x="18" y="26" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="11" fill="var(--gold)" fontWeight="700">{guild?.tag?.slice(0, 2) ?? 'NG'}</text>
              </svg>
              <div>
                <div className="lb3-guild-name">{guild ? `[${guild.tag}] ${guild.name}` : 'No Guild Yet'}</div>
                <div className="lb3-guild-sub">{guildRaidSub}</div>
                <div className="lb3-guild-sub">RANK 14 · 22/30 MEMBERS</div>
              </div>
            </div>
          </div>

        </aside>

      </div>
    </div>
  )
}

function HeroSilhouette() {
  return (
    <svg className="lb3-hero-svg" viewBox="0 0 220 340" aria-hidden="true">
      <ellipse cx="110" cy="332" rx="75" ry="8" fill="rgba(232,160,32,0.12)"/>
      <path d="M82 328 L84 300 L96 300 L98 328 Z" fill="rgba(40,30,20,0.7)" stroke="rgba(232,160,32,0.3)" strokeWidth="1"/>
      <path d="M122 328 L124 300 L136 300 L138 328 Z" fill="rgba(40,30,20,0.7)" stroke="rgba(232,160,32,0.3)" strokeWidth="1"/>
      <path d="M80 300 L78 220 L100 220 L98 300 Z" fill="rgba(50,40,30,0.6)" stroke="rgba(232,160,32,0.2)" strokeWidth="1"/>
      <path d="M120 300 L118 220 L140 220 L138 300 Z" fill="rgba(50,40,30,0.6)" stroke="rgba(232,160,32,0.2)" strokeWidth="1"/>
      <path d="M72 220 L70 160 Q72 128 92 118 L110 115 L128 118 Q148 128 150 160 L148 220 Z" fill="rgba(220,210,190,0.6)" stroke="rgba(232,160,32,0.5)" strokeWidth="1.5"/>
      <ellipse cx="72" cy="158" rx="12" ry="16" fill="rgba(232,160,32,0.25)" stroke="rgba(232,160,32,0.5)" strokeWidth="1.2" transform="rotate(-10, 72, 158)"/>
      <ellipse cx="148" cy="158" rx="12" ry="16" fill="rgba(232,160,32,0.25)" stroke="rgba(232,160,32,0.5)" strokeWidth="1.2" transform="rotate(10, 148, 158)"/>
      <rect x="104" y="104" width="12" height="14" rx="2" fill="rgba(200,185,165,0.5)" stroke="rgba(232,160,32,0.3)" strokeWidth="1"/>
      <path d="M88 90 Q88 60 110 58 Q132 60 132 90 L132 105 L88 105 Z" fill="rgba(50,40,30,0.75)" stroke="rgba(232,160,32,0.5)" strokeWidth="1.5"/>
      <ellipse cx="110" cy="82" rx="16" ry="8" fill="rgba(232,160,32,0.15)" stroke="rgba(232,160,32,0.5)" strokeWidth="1"/>
      <ellipse cx="103" cy="80" rx="3" ry="2" fill="rgba(0,255,224,0.6)"/>
      <ellipse cx="117" cy="80" rx="3" ry="2" fill="rgba(0,255,224,0.6)"/>
    </svg>
  )
}

function MapSVG({ nextCode }: { nextCode: string }) {
  const code = nextCode.toUpperCase().slice(-4)
  return (
    <svg className="lb3-map-svg" viewBox="0 0 680 200" preserveAspectRatio="xMidYMid slice">
      <defs>
        <pattern id="lb3-grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="12" cy="12" r="0.8" fill="rgba(232,160,32,0.15)"/>
        </pattern>
        <radialGradient id="lb3-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#e8a020" stopOpacity="0.2"/>
          <stop offset="100%" stopColor="#e8a020" stopOpacity="0"/>
        </radialGradient>
      </defs>
      <rect width="680" height="200" fill="#171c28"/>
      <rect width="680" height="200" fill="url(#lb3-grid)"/>
      <path d="M 0 140 Q 200 120 400 130 Q 600 140 680 120" stroke="rgba(232,160,32,0.08)" strokeWidth="30" fill="none"/>
      <path d="M 40 155 L 110 125 L 200 105 L 300 85 L 335 78 L 440 74 L 560 68" stroke="rgba(232,160,32,0.3)" strokeWidth="2" fill="none" strokeDasharray="6 3"/>
      {[{x:40,y:155,t:'N.11'},{x:110,y:125,t:'N.12'},{x:200,y:105,t:'N.13'}].map((n) => (
        <g key={n.t}>
          <circle cx={n.x} cy={n.y} r="12" fill="rgba(232,160,32,0.1)" stroke="rgba(232,160,32,0.3)" strokeWidth="1"/>
          <text x={n.x} y={n.y + 3} textAnchor="middle" fontFamily="JetBrains Mono" fontSize="7" fill="rgba(232,160,32,0.6)" fontWeight="600">✓</text>
          <text x={n.x} y={n.y + 17} textAnchor="middle" fontFamily="JetBrains Mono" fontSize="7" fill="rgba(232,160,32,0.5)" letterSpacing="1">{n.t}</text>
        </g>
      ))}
      <circle cx="335" cy="78" r="28" fill="url(#lb3-glow)"/>
      <circle cx="335" cy="78" r="18" fill="rgba(232,160,32,0.12)" stroke="rgba(232,160,32,0.7)" strokeWidth="2">
        <animate attributeName="r" values="16;20;16" dur="3s" repeatCount="indefinite"/>
      </circle>
      <circle cx="335" cy="78" r="10" fill="rgba(232,160,32,0.25)" stroke="#e8a020" strokeWidth="1.5"/>
      <text x="335" y="82" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="7" fill="#e8a020" fontWeight="700">▲</text>
      <text x="335" y="106" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="8" fill="#e8a020" fontWeight="600" letterSpacing="1">{code}</text>
      <circle cx="440" cy="74" r="14" fill="rgba(232,160,32,0.06)" stroke="rgba(232,160,32,0.25)" strokeWidth="1" strokeDasharray="3 2"/>
      <text x="440" y="94" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="7" fill="rgba(232,160,32,0.35)" letterSpacing="1">N.15</text>
      <circle cx="560" cy="68" r="14" fill="rgba(0,0,0,0.04)" stroke="rgba(0,0,0,0.1)" strokeWidth="1"/>
      <text x="560" y="71" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="8" fill="rgba(0,0,0,0.15)">?</text>
      <path d="M370,60 L376,72 L382,60 Z" fill="rgba(200,16,46,0.4)" stroke="rgba(200,16,46,0.6)" strokeWidth="0.8"/>
      <text x="376" y="68" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="6" fill="#c8102e" fontWeight="700">!</text>
    </svg>
  )
}

export default LobbyRoute
