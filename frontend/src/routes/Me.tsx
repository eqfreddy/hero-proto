import { useMe } from '../hooks/useMe'
import { useHeroes } from '../hooks/useHeroes'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiPost } from '../api/client'
import { fetchDaily, type DailyQuest } from '../api/daily'
import { fetchGear, VETERAN_IT_SET } from '../api/gear'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { RarityPill } from '../components/RarityPill'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

const RARITY_ORDER = ['MYTH', 'LEGENDARY', 'EPIC', 'RARE', 'UNCOMMON', 'COMMON']

function rarityRank(r: string) { return RARITY_ORDER.indexOf(r) }

// ── sub-components ───────────────────────────────────────────────────────────

const FACTION_META: Record<string, { label: string; icon: string; color: string }> = {
  EXILE:       { label: 'Exile',       icon: '🌑', color: 'var(--muted)' },
  RESISTANCE:  { label: 'Resistance',  icon: '📡', color: '#4eb8ff' },
  CORP_GREED:  { label: 'Corp Greed',  icon: '📈', color: '#ffd166' },
}

function FactionBadge({ faction }: { faction: string }) {
  const meta = FACTION_META[faction] ?? FACTION_META.EXILE
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
      border: `1px solid color-mix(in srgb, ${meta.color} 50%, transparent)`,
      background: `color-mix(in srgb, ${meta.color} 12%, transparent)`,
      color: meta.color,
    }}>
      {meta.icon} {meta.label}
    </span>
  )
}

function StatCell({ icon, label, value, accent }: { icon: string; label: string; value: string | number; accent?: string }) {
  return (
    <div style={{ padding: '12px 14px', background: 'var(--bg-inset)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>{icon} {label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: accent ?? 'var(--text)', lineHeight: 1 }}>{value}</div>
    </div>
  )
}

function QuickAction({ icon, label, path, color }: { icon: string; label: string; path: string; color: string }) {
  const navigate = useNavigate()
  return (
    <button onClick={() => navigate(path)} style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
      padding: '14px 8px', borderRadius: 'var(--radius)',
      border: `1px solid color-mix(in srgb, ${color} 40%, var(--border))`,
      background: `color-mix(in srgb, ${color} 8%, var(--bg-inset))`,
      flex: 1, cursor: 'pointer',
    }}>
      <span style={{ fontSize: 24 }}>{icon}</span>
      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)' }}>{label}</span>
    </button>
  )
}

function VeteranSetCard({ ownedNames, onJump }: { ownedNames: Set<string>; onJump: () => void }) {
  const owned = VETERAN_IT_SET.filter((p) => ownedNames.has(p.name)).length
  const total = VETERAN_IT_SET.length
  const pct = Math.round((owned / total) * 100)
  const complete = owned === total
  return (
    <div className="card" style={{
      borderColor: complete ? 'var(--r-legendary)' : 'var(--border)',
      borderWidth: complete ? 2 : 1,
      background: complete
        ? 'linear-gradient(180deg, color-mix(in srgb, var(--r-legendary) 12%, var(--panel)) 0%, var(--panel) 60%)'
        : 'var(--panel)',
    }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>
          🏅 Veteran IT Set
        </span>
        <span className="muted" style={{ fontSize: 11 }}>{owned}/{total} {complete && '· COMPLETE'}</span>
      </div>
      <div style={{
        background: 'var(--bg-inset)', borderRadius: 4, height: 4, marginTop: 6, marginBottom: 10, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: complete ? 'var(--r-legendary)' : 'var(--accent)',
          transition: 'width 0.4s ease',
        }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 4 }}>
        {VETERAN_IT_SET.map((p) => {
          const have = ownedNames.has(p.name)
          return (
            <div
              key={p.name}
              title={`${p.name} — ${p.source}`}
              style={{
                aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22,
                background: have ? 'color-mix(in srgb, var(--r-legendary) 18%, var(--bg-inset))' : 'var(--bg-inset)',
                border: `1px solid ${have ? 'var(--r-legendary)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-sm)',
                opacity: have ? 1 : 0.35,
                filter: have ? 'none' : 'grayscale(1)',
              }}
            >
              {p.icon}
            </div>
          )
        })}
      </div>
      <button onClick={onJump} className="secondary" style={{ marginTop: 10, width: '100%', fontSize: 12 }}>
        View Inventory →
      </button>
    </div>
  )
}

function DailyMiniCard({ quests, onClaim }: { quests: DailyQuest[]; onClaim: () => void }) {
  const complete = quests.filter((q) => q.status === 'COMPLETE').length
  const claimed = quests.filter((q) => q.status === 'CLAIMED').length
  const total = quests.length

  const qc = useQueryClient()

  async function claimAll() {
    const claimable = quests.filter((q) => q.status === 'COMPLETE')
    for (const q of claimable) {
      try { await apiPost(`/daily/${q.id}/claim`, {}) } catch {}
    }
    qc.invalidateQueries({ queryKey: ['daily'] })
    qc.invalidateQueries({ queryKey: ['me'] })
    toast.success(`Claimed ${claimable.length} quest${claimable.length !== 1 ? 's' : ''}!`)
    onClaim()
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>📋 Daily Quests</span>
        <span className="muted" style={{ fontSize: 11 }}>{claimed}/{total} claimed</span>
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        {quests.map((q, i) => (
          <div key={i} style={{
            flex: 1, height: 6, borderRadius: 3,
            background: q.status === 'CLAIMED' ? 'var(--good)'
              : q.status === 'COMPLETE' ? 'var(--accent)'
              : 'var(--bg-inset)',
          }} />
        ))}
      </div>
      {quests.slice(0, 3).map((q) => (
        <div key={q.id} style={{ fontSize: 12 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span style={{ color: q.status === 'CLAIMED' ? 'var(--muted)' : 'var(--text)' }}>
              {q.status === 'CLAIMED' ? '✓ ' : ''}{q.kind.replace(/_/g, ' ')}
            </span>
            <span style={{ color: 'var(--warn)', fontSize: 11 }}>
              {q.reward_gems > 0 && `💎${q.reward_gems} `}{q.reward_coins > 0 && `🪙${q.reward_coins}`}
            </span>
          </div>
          <div style={{ background: 'var(--bg-inset)', borderRadius: 2, height: 3, marginTop: 3, overflow: 'hidden' }}>
            <div style={{ height: '100%', background: q.status === 'CLAIMED' ? 'var(--good)' : 'var(--accent)', width: `${Math.min(100, (q.progress / q.goal) * 100)}%` }} />
          </div>
        </div>
      ))}
      {complete > 0 && (
        <button className="primary" onClick={claimAll} style={{ fontSize: 12 }}>
          Claim {complete} ready reward{complete !== 1 ? 's' : ''}
        </button>
      )}
      {complete === 0 && claimed < total && (
        <div className="muted" style={{ fontSize: 11, textAlign: 'center' }}>Keep going — {total - claimed} quest{total - claimed !== 1 ? 's' : ''} left</div>
      )}
      {claimed === total && total > 0 && (
        <div style={{ color: 'var(--good)', fontSize: 12, textAlign: 'center', fontWeight: 600 }}>✓ All done for today!</div>
      )}
    </div>
  )
}

// ── main dashboard ───────────────────────────────────────────────────────────

export function MeRoute() {
  const { data: me, isLoading } = useMe()
  const { data: heroes } = useHeroes()
  const { data: dailyData, refetch: refetchDaily } = useQuery({ queryKey: ['daily'], queryFn: fetchDaily })
  const { data: allGear } = useQuery({ queryKey: ['gear'], queryFn: fetchGear })
  const qc = useQueryClient()
  const navigate = useNavigate()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const [refilling, setRefilling] = useState(false)
  const [claimingBonus, setClaimingBonus] = useState(false)
  const [resending, setResending] = useState(false)

  function logout() {
    clearJwt()
    qc.clear()
    // Land on the marketing site, not the SPA login page.
    window.location.href = '/'
  }

  if (isLoading) return <SkeletonGrid count={6} height={80} />
  if (!me) return <div className="muted">Not signed in.</div>

  const topHeroes = [...(heroes ?? [])]
    .sort((a, b) => rarityRank(a.template.rarity) - rarityRank(b.template.rarity) || b.power - a.power)
    .slice(0, 6)

  const energyPct = Math.min(100, (me.energy / me.energy_cap) * 100)
  const energyColor = energyPct > 60 ? 'var(--good)' : energyPct > 25 ? 'var(--warn)' : 'var(--bad)'

  const winRate = me.arena_wins + me.arena_losses > 0
    ? Math.round((me.arena_wins / (me.arena_wins + me.arena_losses)) * 100)
    : null

  async function refillEnergy() {
    setRefilling(true)
    try {
      await apiPost('/me/refill-energy', { gems: 50 })
      toast.success('Energy refilled!')
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setRefilling(false) }
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

  async function resendVerification() {
    setResending(true)
    try {
      await apiPost('/auth/send-verification', {})
      toast.success('Verification email sent — check your inbox.')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed to send') }
    finally { setResending(false) }
  }

  const username = me.email.split('@')[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Email verification banner ── */}
      {!me.email_verified && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10,
          padding: '12px 16px', borderRadius: 'var(--radius)',
          background: 'color-mix(in srgb, #f4a700 12%, var(--bg-inset))',
          border: '1px solid color-mix(in srgb, #f4a700 40%, transparent)',
        }}>
          <span style={{ fontSize: 13, color: '#f4a700', fontWeight: 600 }}>
            ✉️ Please verify your email to unlock all features.
          </span>
          <button
            onClick={resendVerification}
            disabled={resending}
            style={{
              fontSize: 12, fontWeight: 700, padding: '5px 14px', borderRadius: 99,
              background: '#f4a700', color: '#0b0d10', border: 'none', cursor: 'pointer', flexShrink: 0,
              opacity: resending ? 0.6 : 1,
            }}
          >
            {resending ? 'Sending…' : 'Resend email'}
          </button>
        </div>
      )}

      {/* ── Profile banner ── */}
      <div className="card" style={{
        background: 'linear-gradient(135deg, var(--panel) 0%, var(--panel-2) 100%)',
        borderColor: 'var(--accent)', borderWidth: 1, padding: '20px 24px',
      }}>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Avatar */}
          <div style={{
            width: 64, height: 64, borderRadius: '50%', flexShrink: 0,
            background: 'linear-gradient(135deg, var(--accent), #7c5fff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, fontWeight: 800, color: '#0b0d10',
            boxShadow: '0 0 0 3px rgba(78,161,255,0.3)',
          }}>
            {username.slice(0, 2).toUpperCase()}
          </div>

          {/* Name + level */}
          <div style={{ flex: 1, minWidth: 180 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', lineHeight: 1 }}>{username}</div>
              <FactionBadge faction={me.faction} />
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{me.email}</div>
            <div style={{ marginTop: 10 }}>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>Level {me.account_level}</span>
                <span className="muted" style={{ fontSize: 11 }}>{me.account_xp.toLocaleString()} XP</span>
              </div>
              <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 4,
                  background: 'linear-gradient(90deg, var(--accent), #7c5fff)',
                  width: `${Math.min(100, (me.account_xp % 500) / 5)}%`,
                  transition: 'width 0.4s ease',
                }} />
              </div>
            </div>
          </div>

          {/* Profile stats */}
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--warn)' }}>{me.arena_rating}</div>
              <div className="muted" style={{ fontSize: 11 }}>Arena Rating</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--good)' }}>{me.stages_cleared.length}</div>
              <div className="muted" style={{ fontSize: 11 }}>Stages Cleared</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--r-epic)' }}>{heroes?.length ?? '—'}</div>
              <div className="muted" style={{ fontSize: 11 }}>Heroes</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Main two-column grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Currencies */}
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12 }}>Wallet</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <StatCell icon="💎" label="Gems" value={me.gems.toLocaleString()} accent="var(--accent)" />
              <StatCell icon="✦" label="Shards" value={me.shards.toLocaleString()} accent="var(--r-rare)" />
              <StatCell icon="🪙" label="Coins" value={me.coins.toLocaleString()} accent="var(--warn)" />
              <StatCell icon="🎫" label="Access Cards" value={me.access_cards.toLocaleString()} />
              <StatCell icon="🎟️" label="Free Summons" value={me.free_summon_credits.toLocaleString()} accent="var(--r-epic)" />
              <StatCell icon="🔮" label="Pity Pull" value={me.pulls_since_epic} />
            </div>
          </div>

          {/* Energy */}
          <div className="card">
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>⚡ Energy</div>
              <button onClick={refillEnergy} disabled={refilling} className="secondary" style={{ fontSize: 11 }}>
                {refilling ? '…' : 'Refill 50 💎'}
              </button>
            </div>
            <div style={{ fontSize: 32, fontWeight: 800, color: energyColor, lineHeight: 1, marginBottom: 8 }}>
              {me.energy}<span style={{ fontSize: 16, color: 'var(--muted)', fontWeight: 400 }}> / {me.energy_cap}</span>
            </div>
            <div style={{ background: 'var(--bg-inset)', borderRadius: 6, height: 10, overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 6, background: energyColor,
                width: `${energyPct}%`, transition: 'width 0.4s ease',
              }} />
            </div>
          </div>

          {/* Arena */}
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12 }}>🏟️ Arena</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <StatCell icon="" label="Rating" value={me.arena_rating} accent="var(--warn)" />
              <StatCell icon="⚔️" label="Wins" value={me.arena_wins} accent="var(--good)" />
              <StatCell icon="💀" label="Losses" value={me.arena_losses} accent="var(--bad)" />
            </div>
            {winRate !== null && (
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)', textAlign: 'right' }}>
                Win rate: <strong style={{ color: winRate >= 50 ? 'var(--good)' : 'var(--bad)' }}>{winRate}%</strong>
              </div>
            )}
            <button onClick={() => navigate('/app/arena')} className="secondary" style={{ marginTop: 10, width: '100%', fontSize: 12 }}>
              Go to Arena →
            </button>
          </div>
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Quick actions */}
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12 }}>Quick Actions</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <QuickAction icon="⚔️" label="Battle" path="/app/stages" color="var(--role-atk)" />
              <QuickAction icon="🌀" label="Summon" path="/app/summon" color="var(--r-epic)" />
              <QuickAction icon="🤝" label="Friends" path="/app/friends" color="var(--good)" />
              <QuickAction icon="🛡️" label="Guild" path="/app/guild" color="var(--accent)" />
              <QuickAction icon="🐉" label="Raid" path="/app/raids" color="var(--r-legendary)" />
            </div>
          </div>

          {/* Daily bonus */}
          <div className="card">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>🎁 Daily Login Bonus</div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>Streak login rewards</div>
              </div>
              <button onClick={claimDailyBonus} disabled={claimingBonus} className="primary">
                {claimingBonus ? '…' : 'Claim'}
              </button>
            </div>
          </div>

          {/* Daily quests summary */}
          {dailyData && (
            <DailyMiniCard quests={dailyData} onClaim={() => refetchDaily()} />
          )}

          {/* Veteran IT Set tracker */}
          <VeteranSetCard ownedNames={new Set((allGear ?? []).filter((g) => g.name).map((g) => g.name as string))} onJump={() => navigate('/app/inventory')} />


          {/* Mini roster */}
          {topHeroes.length > 0 && (
            <div className="card">
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
                <span style={{ fontWeight: 700, fontSize: 13 }}>🌟 Top Heroes</span>
                <button onClick={() => navigate('/app/roster')} style={{ fontSize: 11, padding: '3px 10px' }}>View All</button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {topHeroes.map((h) => (
                  <div key={h.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/app/roster/${h.id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/app/roster/${h.id}`) }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 10px', borderRadius: 'var(--radius)',
                      background: 'var(--bg-inset)', cursor: 'pointer',
                      border: '1px solid transparent', transition: 'border-color 0.15s',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border)' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = 'transparent' }}
                  >
                    <img
                      src={`/app/static/heroes/busts/${h.template.code}.png`}
                      alt={h.template.name}
                      style={{ width: 36, height: 36, borderRadius: 'var(--radius-sm)', objectFit: 'cover', background: 'var(--panel-2)' }}
                      onError={(e) => { (e.target as HTMLImageElement).src = `/app/placeholder/hero/${h.template.code}.svg` }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {'⭐'.repeat(Math.min(h.stars, 3))}{h.stars > 3 ? `+${h.stars - 3}` : ''} {h.template.name}
                      </div>
                      <div className="muted" style={{ fontSize: 11 }}>Lv {h.level} · ⚡ {h.power.toLocaleString()}</div>
                    </div>
                    <RarityPill rarity={h.template.rarity} size="sm" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Account ── */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13 }}>Account</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{me.email}</div>
        </div>
        <button
          onClick={logout}
          style={{
            fontSize: 12, padding: '7px 18px',
            background: 'var(--bg-inset)', border: '1px solid var(--border)',
            borderRadius: 20, cursor: 'pointer', color: 'var(--muted)',
            fontWeight: 600, whiteSpace: 'nowrap',
          }}
        >
          Sign out
        </button>
      </div>
    </div>
  )
}
