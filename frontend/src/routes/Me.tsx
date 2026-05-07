// frontend/src/routes/Me.tsx
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { fetchDaily } from '../api/daily'
import { fetchShop, buyProduct, exchangeShards } from '../api/shop'
import { apiPost } from '../api/client'
import { toast } from '../store/ui'
import { RootlordSidebar } from '../components/Layout/RootlordSidebar'
import { RarityPill } from '../components/RarityPill'
import { RecurringResources } from '../components/Me/RecurringResources'
import { useAuthStore } from '../store/auth'
import type { ShopProduct } from '../types'

const LOG_ENTRIES = [
  { tag: '[ARENA]',  color: 'var(--good)',        msg: 'WIN vs shadowkill_99 +12'       },
  { tag: '[SUMMON]', color: 'var(--void-purple)',  msg: 'Pulled: Netrunner [RARE]'       },
  { tag: '[GUILD]',  color: 'var(--accent)',       msg: 'Guild contribution recorded'    },
  { tag: '[ARENA]',  color: 'var(--bad)',          msg: 'LOSS vs DevNull404 -8'          },
  { tag: '[RAID]',   color: 'var(--gold)',         msg: 'Contributed 2,400 dmg to boss'  },
  { tag: '[QUEST]',  color: 'var(--good)',         msg: 'Daily quest completed'           },
]

let _logKey = 0

// ── Top bar ──────────────────────────────────────────────────────────────────

function TopBar() {
  const { data: me } = useMe()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const qc = useQueryClient()
  const [clock, setClock] = useState('')

  useEffect(() => {
    const tick = () => setClock(new Date().toTimeString().slice(0, 8))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  function logout() {
    clearJwt()
    qc.clear()
    window.location.href = '/'
  }

  return (
    <div className="topbar">
      <div className="row">
        <div className="status-dot online" />
        <span className="mono text-sm fw-bold text-accent teal-glow" style={{ letterSpacing: '0.12em' }}>
          SYSTEM::HERO-PROTO
        </span>
      </div>

      {me && (
        <span className="mono text-xs text-muted hide-mobile" style={{ letterSpacing: '0.06em' }}>
          USER <span className="text-accent" style={{ opacity: 0.6 }}>{me.email.split('@')[0]}</span>
          {' | '}LVL <span className="text-accent">{me.account_level}</span>
          {' | '}{me.faction === 'RESISTANCE' ? '📡' : me.faction === 'CORP_GREED' ? '📈' : '🌑'} {me.faction}
        </span>
      )}

      <div className="row" style={{ marginLeft: 'auto', gap: 12 }}>
        {me && (
          <div className="currency-row hide-mobile">
            <span className="gem">💎 {me.gems.toLocaleString()}</span>
            <span className="coin">🪙 {me.coins.toLocaleString()}</span>
            <span className="shard">✦ {me.shards.toLocaleString()}</span>
            <span className="energy">⚡ {me.energy}/{me.energy_cap}</span>
          </div>
        )}
        <span className="mono text-xs text-muted" style={{ paddingLeft: 12, borderLeft: '1px solid var(--border-subtle)' }}>
          {clock}
        </span>
        <button onClick={logout} className="text-muted text-sm fw-bold" style={{ padding: '4px 10px' }}>
          ⏻
        </button>
      </div>
    </div>
  )
}

// ── Zone tabs ─────────────────────────────────────────────────────────────────

type Zone = 'ops' | 'combat' | 'summon' | 'story' | 'guild' | 'raid'

const ZONES: { id: Zone; icon: string; label: string }[] = [
  { id: 'ops',    icon: '⬡', label: 'Ops'    },
  { id: 'combat', icon: '⚔', label: 'Combat' },
  { id: 'summon', icon: '🌀', label: 'Summon' },
  { id: 'story',  icon: '📖', label: 'Story'  },
  { id: 'guild',  icon: '🛡', label: 'Guild'  },
  { id: 'raid',   icon: '🐉', label: 'Raid'   },
]

// ── Action tile ───────────────────────────────────────────────────────────────

function ActionTile({ icon, label, path, color, badge }: { icon: string; label: string; path: string; color: string; badge?: string }) {
  const navigate = useNavigate()
  return (
    <div
      role="button" tabIndex={0}
      onClick={() => navigate(path)}
      onKeyDown={(e) => e.key === 'Enter' && navigate(path)}
      style={{
        background: 'var(--panel-2)',
        border: '1px solid rgba(0,255,224,0.06)',
        borderRadius: 8,
        padding: '18px 10px',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'all 0.2s',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = color
        el.style.transform = 'translateY(-2px)'
        el.style.boxShadow = '0 6px 24px rgba(0,0,0,0.5)'
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = 'rgba(0,255,224,0.06)'
        el.style.transform = 'translateY(0)'
        el.style.boxShadow = 'none'
      }}
    >
      {badge && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          background: 'var(--magenta)', color: '#fff',
          fontSize: 9, fontWeight: 900, padding: '1px 5px', borderRadius: 2,
        }}>{badge}</div>
      )}
      <div style={{ fontSize: 28, marginBottom: 6 }}>{icon}</div>
      <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--muted)' }}>{label}</div>
    </div>
  )
}

// ── Sector: Ops ───────────────────────────────────────────────────────────────

function OpsPanel() {
  const { data: me } = useMe()
  const { data: heroes } = useHeroes()
  const { data: daily, refetch: refetchDaily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily, staleTime: 30_000 })
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [claiming, setClaiming] = useState(false)
  const [claimingBonus, setClaimingBonus] = useState(false)

  if (!me) return null

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'
  const pityPct = Math.min(100, (me.pulls_since_epic / 50) * 100)
  const claimable = (daily ?? []).filter((q) => q.status === 'COMPLETE')
  const claimed = (daily ?? []).filter((q) => q.status === 'CLAIMED').length
  const total = daily?.length ?? 0

  const RARITY_ORDER = ['MYTH', 'LEGENDARY', 'EPIC', 'RARE', 'UNCOMMON', 'COMMON']
  const topHeroes = [...(heroes ?? [])]
    .sort((a, b) => RARITY_ORDER.indexOf(a.template.rarity) - RARITY_ORDER.indexOf(b.template.rarity) || b.power - a.power)
    .slice(0, 6)

  async function claimAll() {
    setClaiming(true)
    let successes = 0
    for (const q of claimable) {
      try {
        await apiPost(`/daily/${q.id}/claim`, {})
        successes++
      } catch {}
    }
    await qc.invalidateQueries({ queryKey: ['daily'] })
    await qc.invalidateQueries({ queryKey: ['me'] })
    refetchDaily()
    if (successes > 0) toast.success(`Claimed ${successes} reward${successes !== 1 ? 's' : ''}!`)
    setClaiming(false)
  }

  async function claimDailyBonus() {
    setClaimingBonus(true)
    try {
      const res = await apiPost<{ reward: Record<string, number> }>('/me/daily-bonus', {})
      const parts = Object.entries(res.reward).filter(([, v]) => v > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Daily bonus: ${parts.join(', ')}` : 'Claimed!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setClaimingBonus(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%', overflowY: 'auto' }}>
      {/* Player strip */}
        <div style={{
          background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)',
          borderRadius: 8, padding: '14px 16px',
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 6, flexShrink: 0,
            background: 'linear-gradient(135deg, rgba(0,255,224,0.2), rgba(155,48,255,0.2))',
            border: '1px solid rgba(0,255,224,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 900, color: 'var(--accent)',
            boxShadow: '0 0 12px rgba(0,255,224,0.15)',
          }}>
            {me.email.slice(0, 2).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>{me.email.split('@')[0]}</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
              Arena {me.arena_rating} · {heroes?.length ?? 0} Heroes · {me.stages_cleared.length} Stages
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 3 }}>
              Lv {me.account_level} · {me.account_xp.toLocaleString()} XP
            </div>
            <div style={{ width: 120, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(100, (me.account_xp % 500) / 5)}%`, background: 'linear-gradient(90deg, var(--accent), var(--void-purple))', borderRadius: 2 }} />
            </div>
          </div>
        </div>

        {/* Command matrix */}
        <div>
          <div className="label-caps" style={{ marginBottom: 8 }}>Command Matrix</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            <ActionTile icon="⚔️" label="Battle"  path="/app/stages" color="var(--magenta)" />
            <ActionTile icon="🌀" label="Summon"  path="/app/summon" color="var(--void-purple)" badge={me.free_summon_credits > 0 ? String(me.free_summon_credits) : undefined} />
            <ActionTile icon="🏟️" label="Arena"   path="/app/arena"  color="var(--warn)" />
            <ActionTile icon="🐉" label="Raid"    path="/app/raids"  color="var(--gold)" />
            <ActionTile icon="🛡️" label="Guild"   path="/app/guild"  color="var(--accent)" />
            <ActionTile icon="📖" label="Story"   path="/app/story"  color="var(--r-epic)" />
          </div>
        </div>

        {/* Status meters */}
        <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
          <div className="label-caps" style={{ marginBottom: 12 }}>System Status</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { label: '⚡ Energy', value: `${me.energy} / ${me.energy_cap}`, pct: energyPct / 100, color: energyColor },
              { label: '🌀 Pity Counter', value: `${me.pulls_since_epic} / 50`, pct: pityPct / 100, color: 'var(--void-purple)' },
              { label: '🏟️ Arena Rating', value: String(me.arena_rating), pct: Math.min(1, me.arena_rating / 4000), color: 'var(--warn)' },
            ].map(({ label, value, pct, color }) => (
              <div key={label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--muted)' }}>{label}</span>
                  <span style={{ fontWeight: 700, color }}>{value}</span>
                </div>
                <div className="meter-bar">
                  <div className="meter-fill" style={{ width: `${pct * 100}%`, background: color, boxShadow: `0 0 6px ${color}60` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <RecurringResources me={me} />

        {/* Top heroes */}
        {topHeroes.length > 0 && (
          <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="label-caps">Top Heroes</div>
              <button onClick={() => navigate('/app/roster')} style={{ fontSize: 10, padding: '3px 8px', color: 'var(--accent)', background: 'transparent', border: '1px solid rgba(0,255,224,0.2)', borderRadius: 4, cursor: 'pointer' }}>
                View All →
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {topHeroes.map((h) => (
                <div
                  key={h.id}
                  role="button" tabIndex={0}
                  onClick={() => navigate(`/app/roster/${h.id}`)}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/app/roster/${h.id}`)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 10px', borderRadius: 6,
                    background: 'var(--bg-inset)', cursor: 'pointer',
                    border: '1px solid transparent', transition: 'border-color 0.15s',
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(0,255,224,0.12)' }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'transparent' }}
                >
                  <img
                    src={`/app/static/heroes/busts/${h.template.code}.png`}
                    alt={h.template.name}
                    style={{ width: 32, height: 32, borderRadius: 4, objectFit: 'cover', background: 'var(--panel-2)' }}
                    onError={(e) => { (e.target as HTMLImageElement).src = `/app/placeholder/hero/${h.template.code}.svg` }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {'⭐'.repeat(Math.min(h.stars, 3))}{h.stars > 3 ? `+${h.stars - 3}` : ''} {h.template.name}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>Lv {h.level} · ⚡ {h.power.toLocaleString()}</div>
                  </div>
                  <RarityPill rarity={h.template.rarity} size="sm" />
                </div>
              ))}
            </div>
          </div>
        )}

      {/* Daily row: login bonus + ops side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 12 }}>
        {/* Daily login bonus */}
        <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(200,16,46,0.2)', borderRadius: 8, padding: '14px 16px' }}>
          <div className="label-caps" style={{ marginBottom: 10 }}>🎁 Daily Login</div>
          <button
            onClick={claimDailyBonus} disabled={claimingBonus}
            style={{
              width: '100%', padding: 8, border: '1px solid rgba(200,16,46,0.4)',
              borderRadius: 4, background: 'rgba(200,16,46,0.12)',
              color: 'var(--crimson)', fontWeight: 900, fontSize: 11,
              letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
            }}
          >
            {claimingBonus ? '…' : 'Claim Daily Bonus'}
          </button>
        </div>

        {/* Daily ops */}
        {daily && (
          <div style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="label-caps">📋 Daily Ops</div>
              <span style={{ fontSize: 10, color: 'var(--good)' }}>{claimed}/{total}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {daily.map((q) => {
                const dotColor = q.status === 'CLAIMED' ? 'var(--good)' : q.status === 'COMPLETE' ? 'var(--accent)' : 'var(--muted)'
                return (
                  <div key={q.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor, marginTop: 4, flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11, color: q.status === 'CLAIMED' ? 'var(--muted)' : 'var(--text)' }}>
                        {q.kind.replace(/_/g, ' ')}
                      </div>
                      <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginTop: 4, overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: dotColor, width: `${Math.min(100, (q.progress / q.goal) * 100)}%` }} />
                      </div>
                    </div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--warn)', flexShrink: 0 }}>
                      {q.reward_gems > 0 ? `💎${q.reward_gems}` : ''}{q.reward_coins > 0 ? `🪙${q.reward_coins}` : ''}
                    </div>
                  </div>
                )
              })}
            </div>
            {claimable.length > 0 && (
              <button
                onClick={claimAll} disabled={claiming}
                className="primary"
                style={{ marginTop: 10, width: '100%', fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                {claiming ? '…' : `Claim ${claimable.length} Ready`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Sector stubs ──────────────────────────────────────────────────────────────

function CombatPanel() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  if (!me) return null
  const winRate = me.arena_wins + me.arena_losses > 0
    ? Math.round((me.arena_wins / (me.arena_wins + me.arena_losses)) * 100) : null
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      {[
        { label: 'Arena Rating', value: me.arena_rating, color: 'var(--warn)' },
        { label: 'Wins', value: me.arena_wins, color: 'var(--good)' },
        { label: 'Losses', value: me.arena_losses, color: 'var(--bad)' },
        { label: 'Win Rate', value: winRate !== null ? `${winRate}%` : '—', color: winRate !== null && winRate >= 50 ? 'var(--good)' : 'var(--bad)' },
        { label: 'Stages Cleared', value: me.stages_cleared.length, color: 'var(--accent)' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{ background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 8, padding: '14px 16px' }}>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 6 }}>{label}</div>
          <div style={{ fontSize: 28, fontWeight: 900, color }}>{value}</div>
        </div>
      ))}
      <button onClick={() => navigate('/app/arena')} className="primary" style={{ gridColumn: '1/-1', padding: 10, fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer' }}>
        ⚔ Enter Arena
      </button>
    </div>
  )
}

function SummonPanel() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  if (!me) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {[
        { label: '🌀 Pity Counter', value: `${me.pulls_since_epic} / 50`, color: 'var(--void-purple)' },
        { label: '🎟️ Free Credits', value: me.free_summon_credits, color: 'var(--r-epic)' },
        { label: '🎫 Access Cards', value: me.access_cards, color: 'var(--text)' },
        { label: '💎 Gems Available', value: me.gems.toLocaleString(), color: 'var(--accent)' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--panel-2)', border: '1px solid rgba(0,255,224,0.06)', borderRadius: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>{label}</span>
          <span style={{ fontSize: 14, fontWeight: 800, color }}>{value}</span>
        </div>
      ))}
      <button onClick={() => navigate('/app/summon')} className="primary" style={{ padding: 10, fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer' }}>
        🌀 Initiate Summon
      </button>
    </div>
  )
}

function StubPanel({ label, path }: { label: string; path: string }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, height: '100%', color: 'var(--muted)' }}>
      <div style={{ fontSize: 48 }}>{label.split(' ')[0]}</div>
      <div style={{ fontSize: 13 }}>{label}</div>
      <button onClick={() => navigate(path)} className="primary" style={{ cursor: 'pointer' }}>Go →</button>
    </div>
  )
}

// ── Right panel: shop + event log ─────────────────────────────────────────────

type ShopTab = 'coins' | 'gems' | 'qol'

function RightPanel() {
  const { data: me } = useMe()
  const { data: shop } = useQuery({ queryKey: ['shop'], queryFn: fetchShop, staleTime: 2 * 60_000 })
  const qc = useQueryClient()
  const [shopTab, setShopTab] = useState<ShopTab>('coins')
  const [buying, setBuying] = useState<string | null>(null)
  const [exchanging, setExchanging] = useState(false)
  const logIdx = useRef(4)

  const [logEntries, setLogEntries] = useState(() => LOG_ENTRIES.slice(0, 4).map(e => ({ ...e, key: _logKey++ })))

  useEffect(() => {
    const id = setInterval(() => {
      setLogEntries((prev) => [{ ...LOG_ENTRIES[logIdx.current % LOG_ENTRIES.length], key: _logKey++ }, ...prev].slice(0, 8))
      logIdx.current++
    }, 9000)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function buy(sku: string) {
    setBuying(sku)
    try {
      const res = await buyProduct(sku)
      const parts = Object.entries(res.granted ?? {}).filter(([, v]) => Number(v) > 0).map(([k, v]) => `+${v} ${k}`)
      toast.success(parts.length ? `Purchased! ${parts.join(', ')}` : 'Purchased!')
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Purchase failed') }
    finally { setBuying(null) }
  }

  async function doExchange() {
    setExchanging(true)
    try {
      const res = await exchangeShards()
      toast.success(`+${res.shards_granted} shards!`)
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Exchange failed') }
    finally { setExchanging(false) }
  }

  if (!me) return null

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'

  const gemProducts = (shop?.products ?? []).filter((p) => p.kind === 'GEM_PACK')
  const coinProducts = (shop?.products ?? []).filter((p) => p.kind === 'COIN_PACK')
  const qolProducts = (shop?.products ?? []).filter((p) => !['GEM_PACK', 'COIN_PACK', 'STARTER_BUNDLE', 'SHARD_PACK', 'ACCESS_CARD_PACK'].includes(p.kind))

  const sx = shop?.shard_exchange

  return (
    <div style={{
      width: 280, flexShrink: 0,
      borderLeft: '1px solid rgba(0,255,224,0.06)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>

        {/* Energy mini */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>
            <span>⚡ Energy</span>
            <span style={{ fontWeight: 700, color: energyColor }}>{me.energy} / {me.energy_cap}</span>
          </div>
          <div className="meter-bar">
            <div className="meter-fill" style={{ width: `${energyPct}%`, background: energyColor, boxShadow: `0 0 4px ${energyColor}60` }} />
          </div>
        </div>

        <div style={{ height: 1, background: 'rgba(0,255,224,0.05)' }} />

        {/* Shop tabs */}
        <div className="label-caps">Shop</div>
        <div style={{ display: 'flex', gap: 3 }}>
          {(['coins', 'gems', 'qol'] as ShopTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setShopTab(t)}
              style={{
                flex: 1, padding: '5px 4px', fontSize: 9, fontWeight: 800,
                letterSpacing: '0.08em', textTransform: 'uppercase',
                border: '1px solid',
                borderColor: shopTab === t ? 'rgba(0,255,224,0.4)' : 'rgba(0,255,224,0.06)',
                borderRadius: 4,
                background: shopTab === t ? 'rgba(0,255,224,0.08)' : 'var(--panel-2)',
                color: shopTab === t ? 'var(--accent)' : 'var(--muted)',
                cursor: 'pointer',
              }}
            >
              {t === 'coins' ? '🪙' : t === 'gems' ? '💎' : '⚙️'} {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* Shop items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {shopTab === 'coins' && coinProducts.map((p) => (
            <ShopItem key={p.sku} product={p} onBuy={buy} buying={buying} />
          ))}
          {shopTab === 'coins' && coinProducts.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic', padding: '8px 0' }}>
              Coin shop coming soon.
            </div>
          )}
          {shopTab === 'gems' && (
            <>
              {sx && (
                <div style={{ padding: '8px 10px', background: 'var(--bg-inset)', border: '1px solid rgba(0,255,224,0.08)', borderRadius: 5, marginBottom: 4 }}>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>
                    {sx.gems_per_batch}💎 → {sx.shards_per_batch}✦ · {sx.remaining_today}/{sx.max_per_day} left today
                  </div>
                  <button
                    onClick={doExchange} disabled={exchanging || sx.remaining_today <= 0}
                    style={{ width: '100%', padding: '5px', fontSize: 10, fontWeight: 700, border: '1px solid rgba(155,48,255,0.3)', borderRadius: 3, background: 'rgba(155,48,255,0.1)', color: 'var(--void-purple)', cursor: 'pointer' }}
                  >
                    {exchanging ? '…' : `Trade ${sx.gems_per_batch}💎 → ${sx.shards_per_batch}✦`}
                  </button>
                </div>
              )}
              {gemProducts.map((p) => <ShopItem key={p.sku} product={p} onBuy={buy} buying={buying} />)}
            </>
          )}
          {shopTab === 'qol' && qolProducts.map((p) => (
            <ShopItem key={p.sku} product={p} onBuy={buy} buying={buying} />
          ))}
        </div>

        <div style={{ height: 1, background: 'rgba(0,255,224,0.05)' }} />

        {/* Live event log */}
        <div className="label-caps">System Log</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {logEntries.map((e, i) => (
            <div key={e.key} style={{
              fontSize: 9, padding: '4px 6px',
              borderLeft: `2px solid ${i === 0 ? e.color : 'rgba(255,255,255,0.04)'}`,
              color: i === 0 ? 'rgba(200,220,255,0.6)' : 'var(--muted)',
              fontFamily: 'Consolas, monospace',
              lineHeight: 1.5,
            }}>
              <span style={{ color: e.color, marginRight: 6 }}>{e.tag}</span>
              {e.msg}
            </div>
          ))}
        </div>

      </div>
    </div>
  )
}

function ShopItem({ product, onBuy, buying }: {
  product: ShopProduct
  onBuy: (sku: string) => void
  buying: string | null
}) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
        background: 'var(--bg-inset)', border: '1px solid rgba(0,255,224,0.06)',
        borderRadius: 5, cursor: 'pointer', transition: 'border-color 0.15s',
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(0,255,224,0.2)' }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(0,255,224,0.06)' }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {product.title}
        </div>
        <div style={{ fontSize: 9, color: 'var(--muted)' }}>{product.description}</div>
      </div>
      <button
        onClick={() => onBuy(product.sku)}
        disabled={buying === product.sku}
        style={{
          flexShrink: 0, padding: '3px 7px', fontSize: 10, fontWeight: 700,
          border: 'none', borderRadius: 3,
          background: 'var(--accent)', color: '#000', cursor: 'pointer',
        }}
      >
        {buying === product.sku ? '…' : product.price_cents === 0 ? 'Free' : `$${(product.price_cents / 100).toFixed(2)}`}
      </button>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export function MeRoute() {
  const [zone, setZone] = useState<Zone>('ops')
  const { data: daily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily, staleTime: 30_000 })

  const claimableBadge = (daily ?? []).filter((q) => q.status === 'COMPLETE').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <RootlordSidebar />

        {/* Center */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Sector tabs */}
          <div style={{
            display: 'flex',
            background: 'rgba(4,6,12,0.8)',
            borderBottom: '1px solid rgba(0,255,224,0.06)',
            flexShrink: 0,
            overflowX: 'auto',
          }}>
            {ZONES.map(({ id, icon, label }) => {
              const badge = id === 'ops' && claimableBadge > 0 ? claimableBadge : null
              return (
                <button
                  key={id}
                  onClick={() => setZone(id)}
                  style={{
                    padding: '0 20px',
                    height: 40,
                    display: 'flex', alignItems: 'center', gap: 7,
                    fontSize: 10, fontWeight: 800,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    color: zone === id ? 'var(--accent)' : 'var(--muted)',
                    background: zone === id ? 'rgba(0,255,224,0.03)' : 'transparent',
                    border: 'none',
                    borderBottom: `2px solid ${zone === id ? 'var(--accent)' : 'transparent'}`,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    textShadow: zone === id ? '0 0 8px rgba(0,255,224,0.5)' : 'none',
                    transition: 'color 0.15s',
                    position: 'relative',
                  }}
                >
                  {icon} {label}
                  {badge !== null && (
                    <span style={{
                      background: 'var(--magenta)', color: '#fff',
                      fontSize: 8, fontWeight: 900, padding: '1px 4px',
                      borderRadius: 2, marginLeft: 2,
                    }}>{badge}</span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Content area */}
          <div style={{ flex: 1, overflow: 'hidden', padding: 16 }}>
            {zone === 'ops'    && <OpsPanel />}
            {zone === 'combat' && <CombatPanel />}
            {zone === 'summon' && <SummonPanel />}
            {zone === 'story'  && <StubPanel label="📖 Story" path="/app/story" />}
            {zone === 'guild'  && <StubPanel label="🛡️ Guild" path="/app/guild" />}
            {zone === 'raid'   && <StubPanel label="🐉 Raids" path="/app/raids" />}
          </div>
        </div>

        <RightPanel />
      </div>
    </div>
  )
}
