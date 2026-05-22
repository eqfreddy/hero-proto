import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { useStages } from '../hooks/useStages'
import { useGuild } from '../hooks/useGuild'
import { useRaid } from '../hooks/useRaid'
import { fetchDaily, type DailyQuest } from '../api/daily'
import { fetchBattlePass, type BPState } from '../api/battlePass'
import { fetchActiveEvent, type ActiveEvent } from '../api/events'
import { assetUrl } from '../api/client'
import { useSoundStore } from '../store/sound'
import type { Hero, Stage } from '../types'
import './Lobby.css'

type RoomAction = {
  label: string
  path: string
}

type RoomCard = {
  key: string
  className: string
  eyebrow: string
  title: string
  summary: string
  status: string
  primary: RoomAction
  secondary: RoomAction
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
  const unclearedUnlocked = stages.find((stage) => stage.unlocked && !stage.cleared)
  return unclearedUnlocked ?? stages[stages.length - 1]
}

function formatHoursWindow(endsAt: string | null | undefined): string {
  if (!endsAt) return 'Stand by'
  const diffMs = new Date(endsAt).getTime() - Date.now()
  if (diffMs <= 0) return 'Closed'
  const totalMinutes = Math.ceil(diffMs / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    return `${days}d ${hours % 24}h`
  }
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatQuestProgress(quest: DailyQuest): string {
  if (quest.status === 'CLAIMED') return 'Claimed'
  if (quest.progress >= quest.goal) return 'Ready'
  return `${quest.progress}/${quest.goal}`
}

function formatQuestName(quest: DailyQuest): string {
  return quest.kind.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function heroPresenceLine(featured: Hero | null, liveEvent: ActiveEvent | null, raidBoss: string | null): string {
  if (featured) {
    const attackKind = featured.template.attack_kind ? ` / ${featured.template.attack_kind}` : ''
    return `${featured.template.role}${attackKind} holding the bridge`
  }
  if (liveEvent) return `${liveEvent.display_name} is pulling traffic to the sector`
  if (raidBoss) return `${raidBoss} is on watch from the outer rim`
  return 'No operative assigned to the bridge yet'
}

function getPressureSignal(
  me: NonNullable<ReturnType<typeof useMe>['data']>,
  liveEvent: ActiveEvent | null,
  nextStage: Stage | null,
): { title: string; body: string; cta: string; path: string } {
  if (me.free_summon_credits > 0) {
    return {
      title: 'Free Pull Primed',
      body: `${me.free_summon_credits} free summon credit${me.free_summon_credits === 1 ? '' : 's'} sitting idle. Cash the hype in while it still feels free.`,
      cta: 'Hit Summon',
      path: '/app/summon',
    }
  }
  if (me.pulls_since_epic >= 40) {
    return {
      title: 'Pity Counter Heating Up',
      body: `${me.pulls_since_epic}/50 pulls since epic. This is exactly where a conversion nudge should feel smart instead of desperate.`,
      cta: 'Open Black Market',
      path: '/app/shop',
    }
  }
  if (liveEvent) {
    return {
      title: `${liveEvent.display_name} Window Open`,
      body: `${formatHoursWindow(liveEvent.ends_at)} left on the event clock. Push story, quests, and summons while the banner still has teeth.`,
      cta: 'Check Event',
      path: '/app/event',
    }
  }
  return {
    title: 'Campaign Heat',
    body: nextStage
      ? `${nextStage.display_name} is the cleanest next win. Energy pressure and team upgrades should both point back into this push.`
      : 'Your next progression spike should come from campaign pressure, not wandering the menus.',
    cta: 'Resume Push',
    path: '/app/stages',
  }
}

function HeroSilhouette() {
  return (
    <svg aria-hidden="true" className="cd-operator-svg" viewBox="0 0 220 280">
      <defs>
        <linearGradient id="silhouetteGlow" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="rgba(94, 234, 212, 0.9)" />
          <stop offset="100%" stopColor="rgba(255, 191, 90, 0.35)" />
        </linearGradient>
      </defs>
      <ellipse cx="110" cy="258" fill="rgba(255,191,90,0.18)" rx="72" ry="10" />
      <path d="M72 248 L82 160 L138 160 L148 248 Z" fill="rgba(8,14,26,0.9)" stroke="url(#silhouetteGlow)" strokeWidth="2" />
      <path d="M78 162 Q84 112 110 110 Q136 112 142 162 Z" fill="rgba(12,18,32,0.95)" stroke="url(#silhouetteGlow)" strokeWidth="2" />
      <circle cx="110" cy="82" fill="rgba(12,18,32,0.95)" r="34" stroke="url(#silhouetteGlow)" strokeWidth="2" />
      <path d="M82 62 Q108 18 144 46 L148 88 L132 80 Q122 100 98 100 L84 88 Z" fill="rgba(20,28,48,0.95)" />
      <path d="M58 168 Q70 128 86 130 L82 192 Z" fill="rgba(9,18,31,0.85)" stroke="rgba(94,234,212,0.35)" strokeWidth="1.5" />
      <path d="M162 168 Q150 128 134 130 L138 192 Z" fill="rgba(9,18,31,0.85)" stroke="rgba(94,234,212,0.35)" strokeWidth="1.5" />
    </svg>
  )
}

export function LobbyRoute() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: stages } = useStages()
  const { data: guildData } = useGuild()
  const { data: raid } = useRaid()
  const { data: daily } = useQuery<DailyQuest[]>({
    queryKey: ['daily'],
    queryFn: fetchDaily,
    staleTime: 60_000,
    retry: 1,
  })
  const { data: bp } = useQuery<BPState>({
    queryKey: ['battle-pass'],
    queryFn: fetchBattlePass,
    staleTime: 120_000,
    retry: 1,
  })
  const { data: activeEvent } = useQuery<ActiveEvent | null>({
    queryKey: ['active-event-detail'],
    queryFn: fetchActiveEvent,
    staleTime: 60_000,
    retry: 1,
  })
  const playBgm = useSoundStore((state) => state.playBgm)

  useEffect(() => {
    playBgm('ancient_map')
  }, [playBgm])

  const featured = useMemo(() => topByPower(heroes, 1)[0] ?? null, [heroes])
  const rosterTop = useMemo(() => topByPower(heroes, 3), [heroes])
  const nextStage = useMemo(() => pickNextStage(stages), [stages])
  const liveEvent = activeEvent && typeof activeEvent.display_name === 'string' ? activeEvent : null
  const guild = guildData?.guild ?? null
  const dailyTop = (daily ?? []).slice(0, 4)
  const claimableDaily = (daily ?? []).filter((quest) => quest.status !== 'CLAIMED' && quest.progress >= quest.goal).length

  if (!me) {
    return (
      <div className="cd">
        <div className="cd-shell">
          <section className="cd-bridge cd-loading">
            <div className="cd-eyebrow">Booting bridge systems</div>
            <h1>Command Deck</h1>
          </section>
        </div>
      </div>
    )
  }

  const pressureSignal = getPressureSignal(me, liveEvent, nextStage)
  const tickerItems = [
    nextStage ? `${nextStage.code} ${nextStage.display_name} ready` : 'Campaign route waiting on new orders',
    raid ? `${raid.boss_name} raid ${String(raid.state).toLowerCase()} - ${formatHoursWindow(raid.ends_at)} left` : 'No live raid pressure',
    guild ? `[${guild.tag}] ${guild.member_count} members on roster` : 'No guild aligned yet',
    liveEvent ? `${liveEvent.display_name} ends in ${formatHoursWindow(liveEvent.ends_at)}` : 'No event takeover active',
    bp?.season ? `${bp.season.code} pass tier ${bp.progress?.current_tier ?? 0}/${bp.season.max_tier}` : 'Battle pass idle',
  ]

  const opsCards = [
    {
      key: 'campaign',
      title: 'Spend Energy',
      detail: `${me.energy}/${me.energy_cap} charge ready`,
      meta: nextStage ? `${nextStage.code} ${nextStage.display_name}` : 'No unlocked node',
      path: '/app/stages',
    },
    {
      key: 'daily',
      title: 'Claim Daily Ops',
      detail: claimableDaily > 0 ? `${claimableDaily} rewards waiting` : `${dailyTop.length} tracked quests`,
      meta: claimableDaily > 0 ? 'Free value on table' : 'Keep the routine moving',
      path: '/app/daily',
    },
    {
      key: 'pvp',
      title: 'Arena Push',
      detail: `${me.arena_tickets}/${me.arena_tickets_cap} tickets`,
      meta: `${me.arena_rating} rating`,
      path: '/app/arena',
    },
    {
      key: 'event',
      title: liveEvent ? 'Event Window' : 'Summon Heat',
      detail: liveEvent ? formatHoursWindow(liveEvent.ends_at) : `${me.pulls_since_epic}/50 pity`,
      meta: liveEvent ? liveEvent.display_name : 'Banner pressure building',
      path: liveEvent ? '/app/event' : '/app/summon',
    },
  ]

  const rooms: RoomCard[] = [
    {
      key: 'bridge',
      className: 'bridge',
      eyebrow: 'Bridge',
      title: 'Command Deck',
      summary: 'Daily routing, quest pressure, current event, and account-wide priorities live here.',
      status: claimableDaily > 0 ? `${claimableDaily} ops ready to claim` : 'Bridge is stable',
      primary: { label: 'Daily Ops', path: '/app/daily' },
      secondary: { label: liveEvent ? 'Event Board' : 'Battle Pass', path: liveEvent ? '/app/event' : '/app/battle-pass' },
    },
    {
      key: 'war',
      className: 'war',
      eyebrow: 'War Room',
      title: 'Holotable',
      summary: 'Campaign, PvP, tower, raids, and the next account-power checkpoint all route through this room.',
      status: raid ? `${raid.boss_name} / ${String(raid.state).toLowerCase()}` : nextStage ? `${nextStage.code} open` : 'Awaiting target lock',
      primary: { label: 'Stages', path: '/app/stages' },
      secondary: { label: 'Arena', path: '/app/arena' },
    },
    {
      key: 'barracks',
      className: 'barracks',
      eyebrow: 'Roster',
      title: 'Barracks',
      summary: 'Heroes, summon, shards, and detail views stay together so progression feels like one loop.',
      status: featured ? `${featured.template.name} / ${fmtBig(featured.power)} power` : 'No lead operative assigned',
      primary: { label: 'Roster', path: '/app/roster' },
      secondary: { label: 'Summon', path: '/app/summon' },
    },
    {
      key: 'forge',
      className: 'forge',
      eyebrow: 'Materials',
      title: 'Droid Forge',
      summary: 'Crafting, inventory, and resource cleanup belong in one room instead of scattered tabs.',
      status: rosterTop.length ? `${rosterTop.length} high-value operators staged` : 'Forge queues are cold',
      primary: { label: 'Crafting', path: '/app/crafting' },
      secondary: { label: 'Inventory', path: '/app/inventory' },
    },
    {
      key: 'market',
      className: 'market',
      eyebrow: 'Economy',
      title: 'Black Market',
      summary: 'Premium currency, pass progress, and targeted conversion pressure should feel like leverage, not spam.',
      status: pressureSignal.title,
      primary: { label: 'Shop', path: '/app/shop' },
      secondary: { label: 'Battle Pass', path: '/app/battle-pass' },
    },
  ]

  return (
    <div className="cd">
      <div className="cd-ticker">
        <span className="cd-ticker-dot" />
        <span className="cd-ticker-label">Fleet Feed</span>
        <div className="cd-ticker-track">
          <div className="cd-ticker-scroll">
            {[...tickerItems, ...tickerItems].map((item, index) => (
              <span key={`${index}-${item}`}>{item} //</span>
            ))}
          </div>
        </div>
      </div>

      <div className="cd-shell">
        <section className="cd-bridge">
          <div className="cd-bridge-copy">
            <div className="cd-eyebrow">Sector command online</div>
            <h1>Command Deck</h1>
            <p className="cd-bridge-text">
              One home. Five rooms. No more scrolling through dead air to figure out what matters.
            </p>
            <div className="cd-bridge-status">
              <div className="cd-status-chip">
                <span className="cd-status-label">Current Push</span>
                <strong>{nextStage ? `${nextStage.code} ${nextStage.display_name}` : 'Acquire next objective'}</strong>
              </div>
              <div className="cd-status-chip">
                <span className="cd-status-label">Bridge Presence</span>
                <strong>{heroPresenceLine(featured, liveEvent, raid?.boss_name ?? null)}</strong>
              </div>
            </div>
            <div className="cd-bridge-actions">
              <button className="cd-btn cd-btn-primary" onClick={() => navigate(nextStage ? '/app/stages' : '/app/summon')}>
                {nextStage ? 'Resume Campaign' : 'Recruit Operative'}
              </button>
              <button className="cd-btn" onClick={() => navigate('/app/arena')}>
                Open Holotable
              </button>
            </div>
          </div>

          <div className="cd-operator">
            <div className="cd-operator-card">
              <div className="cd-operator-viz">
                {featured ? (
                  <img
                    className="cd-operator-bust"
                    src={assetUrl(`/app/static/heroes/busts/${featured.template.code}.png`)}
                    alt={featured.template.name}
                    onError={(event) => {
                      ;(event.currentTarget as HTMLImageElement).style.display = 'none'
                    }}
                  />
                ) : (
                  <HeroSilhouette />
                )}
              </div>
              <div className="cd-operator-meta">
                <span className="cd-operator-tag">Active Operator</span>
                <strong>{featured ? featured.template.name : 'Vacant Bridge Slot'}</strong>
                <span>{featured ? `${featured.template.role} // ${fmtBig(featured.power)} power` : 'Summon or assign a lead hero to anchor the room.'}</span>
              </div>
            </div>
          </div>
        </section>

        <div className="cd-grid">
          <section className="cd-ops">
            <div className="cd-section-head">
              <div>
                <span className="cd-eyebrow">Daily spine</span>
                <h2>Today's Ops</h2>
              </div>
            </div>
            <div className="cd-ops-list">
              {opsCards.map((card) => (
                <button key={card.key} className="cd-op" onClick={() => navigate(card.path)}>
                  <span className="cd-op-title">{card.title}</span>
                  <strong>{card.detail}</strong>
                  <span className="cd-op-meta">{card.meta}</span>
                </button>
              ))}
            </div>

            {dailyTop.length > 0 && (
              <div className="cd-quest-panel">
                <div className="cd-quest-head">
                  <span className="cd-eyebrow">Quest board</span>
                  <button className="cd-inline-link" onClick={() => navigate('/app/daily')}>
                    View All
                  </button>
                </div>
                <div className="cd-quest-list">
                  {dailyTop.map((quest) => (
                    <button key={quest.id} className="cd-quest" onClick={() => navigate('/app/daily')}>
                      <span>{formatQuestName(quest)}</span>
                      <strong>{formatQuestProgress(quest)}</strong>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          <section className="cd-map">
            <div className="cd-section-head">
              <div>
                <span className="cd-eyebrow">Sector map</span>
                <h2>Choose A Room</h2>
              </div>
            </div>

            <div className="cd-room-grid">
              {rooms.map((room) => (
                <article key={room.key} className={`cd-room ${room.className}`}>
                  <div className="cd-room-glow" />
                  <span className="cd-room-eyebrow">{room.eyebrow}</span>
                  <h3>{room.title}</h3>
                  <p>{room.summary}</p>
                  <div className="cd-room-status">{room.status}</div>
                  <div className="cd-room-actions">
                    <button className="cd-chip cd-chip-primary" onClick={() => navigate(room.primary.path)}>
                      {room.primary.label}
                    </button>
                    <button className="cd-chip" onClick={() => navigate(room.secondary.path)}>
                      {room.secondary.label}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <aside className="cd-rail">
            <section className="cd-rail-card">
              <span className="cd-eyebrow">Active pursuit</span>
              <h3>{nextStage ? nextStage.display_name : pressureSignal.title}</h3>
              <p>
                {nextStage
                  ? `Recommended power ${fmtBig(nextStage.recommended_power)}. ${nextStage.energy_cost} energy to probe the node.`
                  : pressureSignal.body}
              </p>
              <button className="cd-btn cd-btn-primary" onClick={() => navigate(nextStage ? '/app/stages' : pressureSignal.path)}>
                {nextStage ? 'Deploy Team' : pressureSignal.cta}
              </button>
            </section>

            <section className="cd-rail-card cd-rail-market">
              <span className="cd-eyebrow">Conversion pressure</span>
              <h3>{pressureSignal.title}</h3>
              <p>{pressureSignal.body}</p>
              <button className="cd-btn" onClick={() => navigate(pressureSignal.path)}>
                {pressureSignal.cta}
              </button>
            </section>

            <section className="cd-rail-card">
              <span className="cd-eyebrow">Signals</span>
              <div className="cd-signal-list">
                <div className="cd-signal-row">
                  <span>Guild</span>
                  <strong>{guild ? `[${guild.tag}] ${guild.member_count} members` : 'Unaligned'}</strong>
                </div>
                <div className="cd-signal-row">
                  <span>Raid</span>
                  <strong>{raid ? `${raid.boss_name} / ${String(raid.state).toLowerCase()}` : 'Offline'}</strong>
                </div>
                <div className="cd-signal-row">
                  <span>Pass</span>
                  <strong>{bp?.season ? `Tier ${bp.progress?.current_tier ?? 0}/${bp.season.max_tier}` : 'Stand by'}</strong>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}
